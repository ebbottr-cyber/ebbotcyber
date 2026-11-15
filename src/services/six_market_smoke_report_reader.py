# -*- coding: utf-8 -*-
"""Admin-only, read-only saved six-market Yahoo fallback smoke report.

Exactly one historical sample per market. No live market request, SQLite, LLM,
report writer or trade. An operator must pin both path and SHA-256 at runtime.
"""
from __future__ import annotations

from datetime import date, timedelta
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import re
from typing import Any

from src.core.trading_calendar import get_trading_dates
from src.services.six_market_live_smoke import PROBES

_MAX_BYTES = 2_000_000
_ISO = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
_SHA256 = re.compile(r"[a-fA-F0-9]{64}\Z")
_STATUS = frozenset({
    "analyzed", "unavailable", "routing_mismatch", "routing_error",
    "calendar_unavailable", "fetch_error", "no_data", "invalid_data",
    "incomplete_or_future_data", "insufficient_history", "stale_price",
    "currency_unverified", "currency_mismatch", "analysis_error",
})
_SPEC = {item.market: item for item in PROBES}


class SixMarketSmokeUnavailable(Exception):
    """No approved read-only file is configured or accessible."""


class SixMarketSmokeInvalid(Exception):
    """The saved report cannot be treated as verified historical evidence."""


def _date(value: Any, *, optional: bool = False) -> date | None:
    if optional and value is None:
        return None
    if not isinstance(value, str) or not _ISO.fullmatch(value):
        raise SixMarketSmokeInvalid("Invalid six-market report date")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise SixMarketSmokeInvalid("Invalid six-market report date") from exc


def _int(value: Any) -> bool:
    return type(value) is int and value >= 0


def _last_completed(market: str, as_of: date) -> date | None:
    """Independent no-network exchange-calendar verification for claimed sessions."""
    try:
        sessions = get_trading_dates(market, as_of - timedelta(days=20), as_of - timedelta(days=1))
        if sessions is None or len(sessions) == 0:
            return None
        return sessions[-1].date()
    except Exception:  # noqa: BLE001 - unavailable exchange calendar is NOT a positive probe
        return None


def validate_six_market_smoke_report(payload: Any) -> dict:
    """Fail closed on inconsistent identity, dates, outcomes and sample counts.

    This verifies an approved report's structure and independent exchange
    sessions, not its remote price provenance or all-market coverage.
    """
    if (not isinstance(payload, dict)
            or payload.get("scope") != "six_market_yahoo_fallback_one_symbol_each"
            or payload.get("source") != "Yahoo Finance"
            or payload.get("checked_markets") != 6
            or not isinstance(payload.get("results"), list)
            or len(payload["results"]) != 6
            or not _int(payload.get("analyzed_markets"))):
        raise SixMarketSmokeInvalid("Invalid six-market report identity or counters")

    as_of = _date(payload.get("as_of"))
    assert isinstance(as_of, date)
    counts = 0
    seen: set[str] = set()
    for item in payload["results"]:
        if not isinstance(item, dict):
            raise SixMarketSmokeInvalid("Malformed market sample")
        market = item.get("market")
        if not isinstance(market, str) or market not in _SPEC or market in seen:
            raise SixMarketSmokeInvalid("Missing, duplicate or unsupported market")
        seen.add(market)
        sample = _SPEC[market]
        status = item.get("status")
        if (item.get("code") != sample.code
                or item.get("yahoo_symbol") != sample.yahoo
                or item.get("currency_expected") != sample.currency
                or not isinstance(status, str) or status not in _STATUS):
            raise SixMarketSmokeInvalid("Unexpected example ticker, currency or outcome")

        # Reject fabricated scores and self-consistent but outdated sessions.
        claimed_session = _date(item.get("expected_last_session"), optional=True)
        last_bar = _date(item.get("last_bar_date"), optional=True)
        bars = item.get("bars")
        score = item.get("technical_score")
        observed = item.get("currency_observed")
        if bars is not None and not _int(bars):
            raise SixMarketSmokeInvalid("Invalid sample candle count")
        if (score is not None and
                (not _int(score) or score > 100)):
            raise SixMarketSmokeInvalid("Invalid sample technical score")
        if (observed is not None and not isinstance(observed, str)):
            raise SixMarketSmokeInvalid("Invalid observed currency")
        if claimed_session is not None:
            if claimed_session >= as_of or (last_bar is not None and last_bar > claimed_session):
                raise SixMarketSmokeInvalid("Contradictory sample dates")
            verified = _last_completed(market, as_of)
            if verified is None or verified != claimed_session:
                raise SixMarketSmokeInvalid("Saved session does not match independent exchange calendar")
        if status == "analyzed":
            if (claimed_session is None or last_bar != claimed_session
                    or not _int(bars) or bars < 60
                    or not _int(score) or score > 100
                    or observed != sample.currency):
                raise SixMarketSmokeInvalid("Unverified market sample claimed an analysis")
            counts += 1
        elif score is not None:
            raise SixMarketSmokeInvalid("Non-analyzed market sample contains technical score")
        if status == "calendar_unavailable" and claimed_session is not None:
            raise SixMarketSmokeInvalid("Calendar-unavailable sample cannot claim a completed session")

    if len(seen) != 6 or counts != payload["analyzed_markets"]:
        raise SixMarketSmokeInvalid("Six-market summary counters do not match actual samples")
    return payload


def load_configured_six_market_smoke_report() -> dict:
    """Load only an operator-configured, sha256-pinned, absolute regular JSON file."""
    configured = os.getenv("SIX_MARKET_SMOKE_REPORT_PATH", "").strip()
    expected = os.getenv("SIX_MARKET_SMOKE_REPORT_SHA256", "").strip()
    if not configured or not expected:
        raise SixMarketSmokeUnavailable("Operator has not approved a saved market report")
    if not _SHA256.fullmatch(expected):
        raise SixMarketSmokeUnavailable("Operator report fingerprint is not configured correctly")
    path = Path(configured)
    if not path.is_absolute():
        raise SixMarketSmokeUnavailable("Approved six-market report path must be absolute")
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
        raise SixMarketSmokeUnavailable("Symlinks are not approved report sources")
    try:
        if not path.is_file() or not 0 < path.stat().st_size <= _MAX_BYTES:
            raise SixMarketSmokeUnavailable("Approved six-market report is missing or oversized")
        with path.open("rb") as stream:
            raw = stream.read(_MAX_BYTES + 1)
        if not 0 < len(raw) <= _MAX_BYTES:
            raise SixMarketSmokeUnavailable("Approved six-market report is empty or oversized")
    except OSError as exc:
        raise SixMarketSmokeUnavailable("Cannot read approved six-market report") from exc

    actual = hashlib.sha256(raw).hexdigest()
    if not hmac.compare_digest(actual, expected.lower()):
        raise SixMarketSmokeInvalid("Approved market report SHA-256 mismatch")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise SixMarketSmokeInvalid("Saved six-market report is not UTF-8 JSON") from exc
    return validate_six_market_smoke_report(payload)
