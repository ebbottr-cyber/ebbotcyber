"""Bounded read-only reader for an operator-approved EBBot equity coverage report.

Does NOT run the audit, inspect broker accounts, read actual OHLCV bars or
return symbol lists. The operator explicitly supplies a local report path.
A report is evidence for a UI summary, not exchange completeness proof.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import re

MARKETS = ("tr", "us", "de", "hk")
MAX_REPORT_BYTES = 8 * 1024 * 1024
PATH_ENV = "EBBOT_EQUITY_COVERAGE_REPORT_PATH"
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class CoverageReportError(ValueError):
    pass


def _missing(reason: str) -> dict:
    return {
        "status": "unavailable",
        "reason": reason,
        "as_of_utc_date": None,
        "markets": {},
        "total_candidate_instruments": None,
        "source_kind": "operator_local_report",
        "listing_completeness_verified": False,
        "licensed_ohlcv_verified": False,
        "paper_trading_enabled": False,
        "live_trading_enabled": False,
    }


def unavailable_equity_coverage_report(reason: str) -> dict:
    """Return safe empty metadata without touching the configured report path."""
    if reason != "administrator_auth_required":
        raise ValueError("unapproved_coverage_unavailable_reason")
    return _missing(reason)


def _whole(value: object) -> int:
    if type(value) is not int or value < 0 or value > 10_000_000:
        raise CoverageReportError("invalid_coverage_count")
    return value


def read_equity_coverage_report(path: str | None = None, *, today: date | None = None) -> dict:
    configured = path if path is not None else os.getenv(PATH_ENV, "")
    if not configured:
        return _missing("operator_report_not_configured")
    candidate = Path(configured)
    if not candidate.is_absolute() or candidate.is_symlink():
        return _missing("unsafe_or_relative_report_path")
    try:
        if not candidate.is_file() or candidate.stat().st_size > MAX_REPORT_BYTES:
            return _missing("report_missing_or_oversized")
        raw = json.loads(candidate.read_text(encoding="utf-8-sig"))
        if not isinstance(raw, dict) or raw.get("status") not in (
            "BLOCKED_INCOMPLETE_EVIDENCE", "REVIEW_ONLY_NEEDS_INDEPENDENT_VALIDATION"
        ):
            raise CoverageReportError("unrecognized_coverage_report")
        if raw.get("selected_markets") != list(MARKETS):
            raise CoverageReportError("unexpected_coverage_markets")
        stamp = raw.get("as_of_utc_date")
        if not isinstance(stamp, str) or not ISO_DATE.fullmatch(stamp):
            raise CoverageReportError("invalid_report_date")
        dated = date.fromisoformat(stamp)
        today = today or datetime.now(timezone.utc).date()
        if dated > today:
            raise CoverageReportError("future_coverage_report")
        market_data = raw.get("markets")
        if not isinstance(market_data, dict) or set(market_data) != set(MARKETS):
            raise CoverageReportError("invalid_market_report_shape")
        summary = {}
        for market in MARKETS:
            item = market_data[market]
            if not isinstance(item, dict):
                raise CoverageReportError("invalid_market_report_item")
            names = (
                "candidate_instruments", "stocks", "etfs", "with_any_ohlcv",
                "with_min_bars", "with_recent_bar", "undated_inventory_count",
                "missing_ohlcv_count", "insufficient_history_count", "stale_ohlcv_count",
            )
            counts = {key: _whole(item.get(key)) for key in names}
            total = counts["candidate_instruments"]
            if (
                counts["stocks"] + counts["etfs"] != total
                or counts["missing_ohlcv_count"] + counts["with_any_ohlcv"] != total
                or any(counts[field] > total for field in names if field != "candidate_instruments")
                or counts["with_min_bars"] > counts["with_any_ohlcv"]
                or counts["with_recent_bar"] > counts["with_any_ohlcv"]
            ):
                raise CoverageReportError("contradictory_market_counts")
            summary[market] = counts
        grand_total = _whole(raw.get("total_candidate_instruments"))
        if grand_total != sum(item["candidate_instruments"] for item in summary.values()):
            raise CoverageReportError("contradictory_total_count")
        return {
            "status": "stale" if (today - dated).days > 7 else "unverified",
            "reason": ("report_over_seven_days_old" if (today - dated).days > 7
                       else "candidate_and_ohlcv_evidence_only"),
            "as_of_utc_date": stamp,
            "markets": summary,
            "total_candidate_instruments": grand_total,
            "source_kind": "operator_local_report",
            "listing_completeness_verified": False,
            "licensed_ohlcv_verified": False,
            "paper_trading_enabled": False,
            "live_trading_enabled": False,
        }
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
        return _missing("unreadable_or_invalid_report")
