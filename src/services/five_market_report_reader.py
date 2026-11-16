# -*- coding: utf-8 -*-
"""Read only an operator-configured ETRE five-market Yahoo sample JSON report.

Never runs a scan, fetches quotes, opens SQLite or accepts an HTTP-provided
filename. A report is historical *sample* evidence, never a trading signal.
"""
from __future__ import annotations

from collections import Counter
from datetime import date
import json
import math
import os
from pathlib import Path
import re
from typing import Any


_MAX_BYTES = 2_000_000
_MARKETS = ("tr", "us", "de", "hk", "jp")
_CURRENCIES = {"tr": "TRY", "us": "USD", "de": "EUR", "hk": "HKD", "jp": "JPY"}
_PATTERNS = {
    "tr": re.compile(r"[A-Z]{4,5}\.IS\Z"),
    "us": re.compile(r"[A-Z]{1,5}(?:\.[A-Z])?\Z"),
    "de": re.compile(r"[A-Z][A-Z0-9]{0,7}\.DE\Z"),
    "hk": re.compile(r"HK[0-9]{5}\Z"),
    "jp": re.compile(r"[0-9]{4,5}\.T\Z"),
}
_CORE = ("THYAO.IS", "AAPL", "SAP.DE", "HK00700", "7203.T")
_EXTRA = ("ASELS.IS", "MSFT", "SIE.DE", "HK01810", "6758.T")
_SCOPES = {
    "etre_five_market_core_historical_samples": _CORE,
    "etre_five_market_expanded_historical_samples": _CORE + _EXTRA,
    "etre_five_market_custom_historical_symbols": None,
}
_STATUSES = frozenset({
    "analyzed", "unavailable", "routing_mismatch", "routing_error",
    "calendar_unavailable", "fetch_error", "no_data", "invalid_data",
    "incomplete_or_future_data", "insufficient_history", "stale_price",
    "currency_unverified", "currency_mismatch", "analysis_error",
})


class FiveMarketReportUnavailable(Exception):
    """No configured five-market JSON file is available for admin display."""


class FiveMarketReportInvalid(Exception):
    """Configured JSON has an unsupported or contradictory shape."""


def _iso_date(value: Any) -> date:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise FiveMarketReportInvalid("Invalid report/session date")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise FiveMarketReportInvalid("Invalid report/session date") from exc


def _nonnegative(value: Any) -> bool:
    return type(value) is int and 0 <= value <= 100_000


def _yahoo_code(market: str, code: str) -> str:
    if market != "hk":
        return code
    return f"{int(code[2:]):04d}.HK"


def validate_five_market_sample_report(payload: Any) -> dict:
    """Validate identities, status evidence and summary counters (not provenance)."""
    if not isinstance(payload, dict):
        raise FiveMarketReportInvalid("Expected JSON object")
    scope = payload.get("scope")
    if (scope not in _SCOPES or payload.get("source") != "Yahoo Finance"
            or payload.get("market_scope") != list(_MARKETS)):
        raise FiveMarketReportInvalid("Unsupported five-market report identity")
    as_of = _iso_date(payload.get("as_of"))
    rows = payload.get("results")
    if not isinstance(rows, list) or not 1 <= len(rows) <= 50:
        raise FiveMarketReportInvalid("Invalid number of report rows")
    if (not _nonnegative(payload.get("checked_symbols"))
            or payload["checked_symbols"] != len(rows)
            or not _nonnegative(payload.get("analyzed_symbols"))
            or not _nonnegative(payload.get("markets_checked"))):
        raise FiveMarketReportInvalid("Invalid report counters")

    seen: set[str] = set()
    totals: dict[str, Counter[str]] = {market: Counter() for market in _MARKETS}
    for item in rows:
        if not isinstance(item, dict):
            raise FiveMarketReportInvalid("Invalid stock row")
        market, code, status = item.get("market"), item.get("code"), item.get("status")
        if (market not in _MARKETS or not isinstance(code, str)
                or not _PATTERNS[market].fullmatch(code)
                or code in seen or status not in _STATUSES
                or item.get("yahoo_symbol") != _yahoo_code(market, code)
                or item.get("currency_expected") != _CURRENCIES[market]):
            raise FiveMarketReportInvalid("Invalid, duplicate or out-of-scope symbol")
        seen.add(code)
        totals[market][status] += 1
        bars = item.get("bars")
        if bars is not None and not _nonnegative(bars):
            raise FiveMarketReportInvalid("Invalid OHLCV bar count")
        session = item.get("expected_last_session")
        last = item.get("last_bar_date")
        if session is not None:
            session = _iso_date(session)
            if session > as_of:
                raise FiveMarketReportInvalid("Future session")
        if last is not None:
            last = _iso_date(last)
            if last > as_of or (session is not None and last > session):
                raise FiveMarketReportInvalid("Future or incomplete candle")
        observed = item.get("currency_observed")
        if observed is not None and (
            not isinstance(observed, str) or
            not re.fullmatch(r"[A-Z]{3}", observed)
        ):
            raise FiveMarketReportInvalid("Invalid observed currency")
        error_type = item.get("error_type")
        if error_type is not None and (
            not isinstance(error_type, str) or len(error_type) > 100
        ):
            raise FiveMarketReportInvalid("Invalid error type")
        score = item.get("technical_score")
        if status == "analyzed":
            if (bars is None or bars < 60 or session is None or last != session
                    or observed != _CURRENCIES[market] or type(score) is not int
                    or not 0 <= score <= 100):
                raise FiveMarketReportInvalid("Success without validated history")
        elif score is not None:
            raise FiveMarketReportInvalid("Failed row must not have a technical score")

    if _SCOPES[scope] is not None and set(seen) != set(_SCOPES[scope]):
        raise FiveMarketReportInvalid("Fixed sample set membership mismatch")
    checked_markets = sum(bool(totals[market]) for market in _MARKETS)
    analyzed = sum(counter.get("analyzed", 0) for counter in totals.values())
    if (payload["markets_checked"] != checked_markets
            or payload["analyzed_symbols"] != analyzed):
        raise FiveMarketReportInvalid("Summary counts do not match stock rows")

    summaries = payload.get("by_market")
    if not isinstance(summaries, dict) or set(summaries) != set(_MARKETS):
        raise FiveMarketReportInvalid("Missing or unexpected market summary")
    for market in _MARKETS:
        raw = summaries[market]
        counts = totals[market]
        checked = sum(counts.values())
        passed = counts.get("analyzed", 0)
        status = (
            "not_requested" if not checked else
            "samples_passed" if checked == passed else
            "partial" if passed else "samples_failed"
        )
        failures = dict(sorted((key, n) for key, n in counts.items() if key != "analyzed"))
        if (not isinstance(raw, dict)
                or raw.get("checked_symbols") != checked
                or raw.get("analyzed_symbols") != passed
                or raw.get("sample_status") != status
                or raw.get("failure_status_counts") != failures):
            raise FiveMarketReportInvalid("Market summary contradicts stock results")
    # Return only a validated, bounded subset: never expose arbitrary JSON
    # keys or fields if someone supplies an over-populated report.
    safe_rows = []
    for row in rows:
        safe_rows.append({key: row[key] for key in (
            "market", "code", "yahoo_symbol", "currency_expected", "status",
            "bars", "expected_last_session", "last_bar_date",
            "currency_observed", "technical_score", "error_type",
        ) if key in row})
    return {
        "scope": scope,
        "source": "Yahoo Finance",
        "as_of": as_of.isoformat(),
        "checked_symbols": len(rows),
        "analyzed_symbols": analyzed,
        "markets_checked": checked_markets,
        "market_scope": list(_MARKETS),
        "results": safe_rows,
        "by_market": {market: {
            "checked_symbols": sum(totals[market].values()),
            "analyzed_symbols": totals[market].get("analyzed", 0),
            "sample_status": summaries[market]["sample_status"],
            "failure_status_counts": summaries[market]["failure_status_counts"],
        } for market in _MARKETS},
    }


def load_configured_five_market_sample_report() -> dict:
    """Fail closed unless an admin has configured an absolute report filepath."""
    configured = os.getenv("ETRE_FIVE_MARKET_REPORT_PATH", "").strip()
    if not configured:
        raise FiveMarketReportUnavailable("No sample report configured")
    path = Path(configured)
    if not path.is_absolute():
        raise FiveMarketReportUnavailable("Sample report path must be absolute")
    try:
        if not path.is_file() or path.stat().st_size > _MAX_BYTES:
            raise FiveMarketReportUnavailable("Sample report missing or too large")
        with path.open("rb") as handle:
            raw = handle.read(_MAX_BYTES + 1)
        if len(raw) > _MAX_BYTES:
            raise FiveMarketReportUnavailable("Sample report too large")
        return validate_five_market_sample_report(json.loads(raw.decode("utf-8")))
    except FiveMarketReportInvalid:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FiveMarketReportInvalid("Unreadable sample report") from exc
