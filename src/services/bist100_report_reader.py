# -*- coding: utf-8 -*-
"""Read an explicitly configured BIST100 OHLCV audit, without any network I/O.

The report is produced by src.services.bist100_coverage CLI.  This module
never runs the audit, accepts a client-controlled path, or treats a quote as
an AI-analysis result.  It validates counters and membership before serving.
"""
from __future__ import annotations

from collections import Counter
from datetime import date
import json
import os
from pathlib import Path
import re
from typing import Any

from src.services.bist100_universe import load_bist100_universe

_MAX_BYTES = 2_000_000
_ALLOWED_STATUSES = frozenset({
    "ready", "fetch_error", "no_data", "invalid_data", "no_completed_bars",
    "currency_mismatch", "currency_unverified", "calendar_unavailable",
    "stale_price", "insufficient_history",
})
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")


class CoverageReportUnavailable(Exception):
    """No configured local BIST100 audit file is available."""


class CoverageReportInvalid(Exception):
    """The configured local audit is not a trustworthy report shape."""


def _date(value: Any, *, optional: bool = False) -> date | None:
    if optional and value is None:
        return None
    if not isinstance(value, str) or not _ISO_DATE.fullmatch(value):
        raise CoverageReportInvalid("Invalid date in BIST100 coverage report")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise CoverageReportInvalid("Invalid date in BIST100 coverage report") from exc


def _count(value: Any) -> bool:
    return type(value) is int and value >= 0


def validate_coverage_report(payload: Any) -> dict:
    """Validate counters, dated members, OHLCV metadata and status honesty."""
    if not isinstance(payload, dict):
        raise CoverageReportInvalid("Expected JSON object")
    for key, wanted in {
        "index": "BIST100", "source": "Yahoo Finance", "currency_expected": "TRY",
        "calendar": "XIST", "timezone": "Europe/Istanbul", "universe_total": 100,
    }.items():
        if payload.get(key) != wanted:
            raise CoverageReportInvalid(f"Unexpected report field: {key}")
    as_of = _date(payload.get("as_of"))
    assert isinstance(as_of, date)
    try:
        universe = load_bist100_universe(as_of)
    except (ValueError, OSError, KeyError) as exc:
        raise CoverageReportInvalid("Snapshot does not cover report date") from exc
    rows = payload.get("results")
    if not isinstance(rows, list) or len(rows) > 100:
        raise CoverageReportInvalid("Invalid BIST100 result rows")
    checked = payload.get("checked")
    remaining = payload.get("remaining")
    ready = payload.get("ready")
    valid_bars = payload.get("with_valid_price_bars")
    if (not all(_count(v) for v in (checked, remaining, ready, valid_bars))
            or checked != len(rows) or remaining != 100 - checked
            or type(payload.get("complete")) is not bool
            or payload["complete"] != (checked == 100)):
        raise CoverageReportInvalid("Invalid BIST100 scan counters")
    min_bars = payload.get("min_bars")
    if not _count(min_bars) or min_bars < 1:
        raise CoverageReportInvalid("Invalid minimum bar count")
    expected_last = _date(payload.get("expected_last_completed_session"), optional=True)
    if expected_last is not None and expected_last > as_of:
        raise CoverageReportInvalid("Future expected session")
    seen: set[str] = set()
    counts: Counter[str] = Counter()
    for item in rows:
        if not isinstance(item, dict):
            raise CoverageReportInvalid("Invalid stock row")
        symbol = item.get("symbol")
        status = item.get("status")
        if (not isinstance(symbol, str) or symbol not in universe.symbols
                or symbol in seen or status not in _ALLOWED_STATUSES):
            raise CoverageReportInvalid("Duplicate or unsupported BIST100 stock/status")
        seen.add(symbol)
        counts[status] += 1
        bar_count = item.get("rows")
        if not _count(bar_count):
            raise CoverageReportInvalid("Invalid OHLCV row count")
        first = _date(item.get("first_bar_date"), optional=True)
        last = _date(item.get("last_bar_date"), optional=True)
        if (bar_count > 0) != (first is not None and last is not None):
            raise CoverageReportInvalid("OHLCV rows and dates mismatch")
        if (first is None) != (last is None):
            raise CoverageReportInvalid("Incomplete OHLCV date range")
        if first is not None and (first > last or last > as_of):
            raise CoverageReportInvalid("Invalid OHLCV date range")
        if item.get("expected_last_session") != payload.get("expected_last_completed_session"):
            raise CoverageReportInvalid("Session metadata mismatch")
        currency = item.get("observed_currency")
        if currency is not None and not isinstance(currency, str):
            raise CoverageReportInvalid("Invalid currency metadata")
        issues = item.get("issues")
        if not isinstance(issues, list) or any(not isinstance(v, str) for v in issues):
            raise CoverageReportInvalid("Invalid data-quality issues")
        if status == "ready" and (
            bar_count < min_bars or currency != "TRY"
            or last is None or last != expected_last or issues
        ):
            raise CoverageReportInvalid("Unsupported ready status")
    summaries = payload.get("status_counts")
    if (not isinstance(summaries, dict) or summaries != dict(counts)
            or ready != counts.get("ready", 0)
            or valid_bars != sum(item["rows"] > 0 for item in rows)):
        raise CoverageReportInvalid("Report summary does not match stock rows")
    return payload


def load_configured_coverage_report() -> dict:
    """Read only an operator-configured absolute file path, max 2 MB.

    Returns missing instead of falsely returning an empty 100-member scan.
    The user cannot select a server path through an HTTP query.
    """
    configured = os.getenv("BIST100_COVERAGE_REPORT_PATH", "").strip()
    if not configured:
        raise CoverageReportUnavailable("No BIST100 report configured")
    path = Path(configured)
    if not path.is_absolute():
        raise CoverageReportUnavailable("BIST100 report path must be absolute")
    try:
        if not path.is_file() or path.stat().st_size > _MAX_BYTES:
            raise CoverageReportUnavailable("BIST100 report missing or too large")
        with path.open("rb") as handle:
            raw = handle.read(_MAX_BYTES + 1)
        if len(raw) > _MAX_BYTES:
            raise CoverageReportUnavailable("BIST100 report too large")
        return validate_coverage_report(json.loads(raw.decode("utf-8")))
    except CoverageReportInvalid:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CoverageReportInvalid("BIST100 report unreadable or invalid JSON") from exc
