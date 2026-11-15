# -*- coding: utf-8 -*-
"""Validate and read a saved BIST100 technical ranking; never run a live scan.

Only an operator-configured absolute JSON file can be served to an authenticated
admin. This module never opens SQLite or calls any pricing/LLM/trading service.
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

from src.services.bist100_universe import load_bist100_universe

_MAX_BYTES = 2_000_000
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
_STATUSES = frozenset({
    "analyzed", "not_imported", "db_error", "unverified_source",
    "invalid_data", "insufficient_history", "stale_price", "analysis_error",
})
_TRENDS = frozenset({
    "Güçlü yükseliş", "Yükseliş", "Zayıf yükseliş", "Yatay",
    "Zayıf düşüş", "Düşüş", "Güçlü düşüş",
})
_SIGNALS = frozenset({
    "Güçlü alım sinyali", "Alım sinyali", "Tut", "İzle",
    "Satış sinyali", "Güçlü satış sinyali",
})


class TechnicalReportUnavailable(Exception):
    """No local technical ranking has been configured for display."""


class TechnicalReportInvalid(Exception):
    """A local technical report has a contradictory or invalid shape."""


def _date(value: Any) -> date:
    if not isinstance(value, str) or not _DATE_RE.fullmatch(value):
        raise TechnicalReportInvalid("Invalid technical report date")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise TechnicalReportInvalid("Invalid technical report date") from exc


def _count(value: Any) -> bool:
    return type(value) is int and value >= 0


def _finite(value: Any) -> bool:
    return type(value) in (float, int) and math.isfinite(value)


def _validate_analyzed(row: dict, last_session: date) -> None:
    if not _count(row.get("bars")) or row["bars"] < 60:
        raise TechnicalReportInvalid("Insufficient technical history")
    if _date(row.get("last_bar_date")) != last_session:
        raise TechnicalReportInvalid("Stale or inconsistent analyzed session")
    if not _count(row.get("score")) or row["score"] > 100:
        raise TechnicalReportInvalid("Invalid technical score")
    for field in ("close_try", "ma5_try", "ma20_try", "rsi12",
                  "macd_histogram", "bias_ma5_pct"):
        if not _finite(row.get(field)):
            raise TechnicalReportInvalid("Invalid technical indicators")
    if (min(row["close_try"], row["ma5_try"], row["ma20_try"]) <= 0
            or not 0 <= row["rsi12"] <= 100):
        raise TechnicalReportInvalid("Out-of-range technical indicators")
    if row.get("trend") not in _TRENDS or row.get("technical_signal") not in _SIGNALS:
        raise TechnicalReportInvalid("Unrecognized technical labels")
    if type(row.get("chase_risk")) is not bool or type(row.get("eligible_for_watchlist")) is not bool:
        raise TechnicalReportInvalid("Invalid watchlist eligibility flags")
    if row["chase_risk"] and row["eligible_for_watchlist"]:
        raise TechnicalReportInvalid("Chase-risk stock cannot be watchlist eligible")
    # Report percentages are rounded to two decimals, so allow the original
    # raw precision to differ by 0.005 at the 5% boundary.
    if row["bias_ma5_pct"] > 5.01 and not row["chase_risk"]:
        raise TechnicalReportInvalid("Missing MA5 chase-risk flag")
    if row["bias_ma5_pct"] < 4.99 and row["chase_risk"]:
        raise TechnicalReportInvalid("Contradictory MA5 chase-risk flag")


def validate_technical_report(payload: Any) -> dict:
    """Reject forged counters, invalid dates, members, ranking and risk flags."""
    if not isinstance(payload, dict):
        raise TechnicalReportInvalid("Expected JSON object")
    if (payload.get("index") != "BIST100"
            or payload.get("mode") != "read_only_local_sqlite"
            or payload.get("universe_total") != 100):
        raise TechnicalReportInvalid("Unexpected BIST100 technical report identity")
    as_of = _date(payload.get("as_of"))
    session = _date(payload.get("last_completed_session"))
    if session >= as_of:
        raise TechnicalReportInvalid("Expected a previous completed session")
    try:
        members = set(load_bist100_universe(as_of).symbols)
    except (ValueError, OSError, KeyError) as exc:
        raise TechnicalReportInvalid("No valid membership snapshot") from exc

    rows = payload.get("results")
    ranking = payload.get("ranking")
    if not isinstance(rows, list) or not isinstance(ranking, list) or len(rows) > 100:
        raise TechnicalReportInvalid("Invalid rows or ranking")
    checked, remaining, analyzed, eligible = (
        payload.get(k) for k in ("checked", "remaining", "analyzed", "watchlist_eligible")
    )
    if (not all(_count(x) for x in (checked, remaining, analyzed, eligible))
            or checked != len(rows) or checked < 1
            or remaining != 100 - checked
            or analyzed != len(ranking) or eligible > analyzed):
        raise TechnicalReportInvalid("Inconsistent report counters")

    seen: set[str] = set()
    counts: Counter[str] = Counter()
    analyzed_by_symbol: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise TechnicalReportInvalid("Invalid stock row")
        code, status = row.get("symbol"), row.get("status")
        if (not isinstance(code, str) or code not in members or code in seen
                or status not in _STATUSES):
            raise TechnicalReportInvalid("Unknown, duplicate or unsupported stock/status")
        seen.add(code)
        counts[status] += 1
        if status == "analyzed":
            _validate_analyzed(row, session)
            analyzed_by_symbol[code] = row

    if (payload.get("status_counts") != dict(counts)
            or analyzed != counts.get("analyzed", 0)
            or eligible != sum(
                1 for row in analyzed_by_symbol.values()
                if row["eligible_for_watchlist"]
            )):
        raise TechnicalReportInvalid("Technical summary does not match stock rows")

    ordered = sorted(analyzed_by_symbol.values(), key=lambda r: (-r["score"], r["symbol"]))
    for position, item in enumerate(ranking, start=1):
        if not isinstance(item, dict) or item.get("rank") != position:
            raise TechnicalReportInvalid("Wrong technical rank")
        if {k: v for k, v in item.items() if k != "rank"} != ordered[position - 1]:
            raise TechnicalReportInvalid("Ranking differs from analyzed records")
    return payload


def load_configured_technical_report() -> dict:
    """Load one operator-approved absolute JSON path, at most 2 MB."""
    configured = os.getenv("BIST100_TECHNICAL_REPORT_PATH", "").strip()
    if not configured:
        raise TechnicalReportUnavailable("Technical report not configured")
    path = Path(configured)
    if not path.is_absolute():
        raise TechnicalReportUnavailable("Technical report path must be absolute")
    try:
        if not path.is_file() or path.stat().st_size > _MAX_BYTES:
            raise TechnicalReportUnavailable("Technical report missing or too large")
        with path.open("rb") as handle:
            raw = handle.read(_MAX_BYTES + 1)
        if len(raw) > _MAX_BYTES:
            raise TechnicalReportUnavailable("Technical report too large")
        return validate_technical_report(json.loads(raw.decode("utf-8")))
    except TechnicalReportInvalid:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TechnicalReportInvalid("Unreadable technical report") from exc
