"""Offline, fail-closed multi-day public-source observation continuity audit.

The input consists ONLY of real saved JSON observations produced by
scripts.audit_tr_fx_public_sources. Each observation has an actual timestamp.
Repeated snapshots on the same date do not count as extra independent days.
Missing dates are not inferred without an explicit expected-date list; market
holidays and weekends are not automatically assumed to be trading sessions.

No network, orders, account valuation, broker access, scheduler, persistence,
paper fills, or profitability inference. A PASS is never a trading-readiness gate.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date, datetime
import json
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from scripts.audit_tr_fx_cross_sources import _tcmb, _unique_by, _yahoo

ISTANBUL = ZoneInfo("Europe/Istanbul")
MAX_FILES = 30
MAX_FILE_BYTES = 1_000_000
SOURCES = (
    ("bist100", "yahoo", "XU100.IS"),
    ("bist30", "yahoo", "XU030.IS"),
    ("usdtry", "yahoo", "TRY=X"),
    ("eurtry", "yahoo", "EURTRY=X"),
    ("USD", "tcmb", "USD"),
    ("EUR", "tcmb", "EUR"),
    ("CNY", "tcmb", "CNY"),
)


def _observation_date(snapshot: Any) -> tuple[str, str]:
    if not isinstance(snapshot, dict):
        raise ValueError("invalid_observation_document")
    if snapshot.get("status") not in ("READ_ONLY_OBSERVATION", "NO_VALID_PROVIDER_QUOTES"):
        raise ValueError("not_an_observation")
    if (snapshot.get("research_only") is not True
            or snapshot.get("prices_executable") is not False
            or snapshot.get("paper_trading_enabled") is not False
            or snapshot.get("live_trading_enabled") is not False
            or snapshot.get("scheduler_enabled") is not False):
        raise ValueError("unsafe_observation_flags")
    for key in ("orders", "paper_fills", "journal_writes"):
        if type(snapshot.get(key)) is not int or snapshot[key] != 0:
            raise ValueError("unexpected_execution_evidence")

    observed = snapshot.get("observed_at_istanbul")
    as_of = snapshot.get("as_of_local_date")
    if not isinstance(observed, str) or not isinstance(as_of, str):
        raise ValueError("missing_observation_timestamp")
    try:
        timestamp = datetime.fromisoformat(observed)
        local_date = date.fromisoformat(as_of)
    except ValueError as exc:
        raise ValueError("malformed_observation_timestamp") from exc
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("observation_timestamp_without_timezone")
    if timestamp.astimezone(ISTANBUL).date() != local_date:
        raise ValueError("timestamp_local_date_disagreement")
    return as_of, timestamp.astimezone(ISTANBUL).isoformat()


def _source_available(doc: dict, date_str: str, source: tuple[str, str, str]) -> bool:
    key, kind, symbol = source
    today = date.fromisoformat(date_str)
    if kind == "yahoo":
        market = doc.get("market_daily")
        rows = _unique_by(market.get("checks"), "key") if isinstance(market, dict) else {}
        return _yahoo(rows.get(key), symbol, today) is not None
    official = doc.get("official_tcmb")
    rows = _unique_by(official.get("checks"), "currency") if isinstance(official, dict) else {}
    return _tcmb(rows.get(key), symbol, today) is not None


def summarize_continuity(
    snapshots: list[Any], *, expected_dates: list[str] | None = None,
) -> dict[str, Any]:
    """Return conservative source-day evidence, never invented market samples."""
    if not 1 <= len(snapshots) <= MAX_FILES:
        raise ValueError("observation_count_out_of_bounds")
    by_date: dict[str, list[dict]] = defaultdict(list)
    seen_times: set[str] = set()
    for doc in snapshots:
        d, timestamp = _observation_date(doc)
        if timestamp in seen_times:
            raise ValueError("duplicate_observation_instant")
        seen_times.add(timestamp)
        by_date[d].append(doc)

    explicit_dates: list[str] | None = None
    if expected_dates is not None:
        if len(expected_dates) > MAX_FILES or not expected_dates:
            raise ValueError("expected_date_count_out_of_bounds")
        parsed = []
        for raw in expected_dates:
            if not isinstance(raw, str):
                raise ValueError("invalid_expected_date")
            try:
                if date.fromisoformat(raw).isoformat() != raw:
                    raise ValueError("invalid_expected_date")
            except ValueError as exc:
                raise ValueError("invalid_expected_date") from exc
            parsed.append(raw)
        if len(set(parsed)) != len(parsed):
            raise ValueError("duplicate_expected_date")
        explicit_dates = sorted(parsed)

    observed_dates = sorted(by_date)
    if explicit_dates is not None and any(d not in explicit_dates for d in observed_dates):
        raise ValueError("observed_date_not_in_explicit_expected_dates")

    days: list[dict[str, Any]] = []
    issues: set[str] = set()
    for d in observed_dates:
        docs = by_date[d]
        evidence: dict[str, dict[str, Any]] = {}
        for key, kind, symbol in SOURCES:
            flags = [_source_available(doc, d, (key, kind, symbol)) for doc in docs]
            if all(flags):
                status = "observed_indicative_only"
            elif any(flags):
                status = "intermittent_within_day"
                issues.add(f"{key}_intermittent_{d}")
            else:
                status = "missing_or_unverified"
                issues.add(f"{key}_missing_{d}")
            evidence[key] = {
                "status": status,
                "observation_count": len(flags),
                "observed_count": sum(flags),
                "independent_second_source_verified": False,
            }
        days.append({
            "date": d,
            "observation_count": len(docs),
            "complete_indicative_source_coverage": all(
                r["status"] == "observed_indicative_only" for r in evidence.values()
            ),
            "sources": evidence,
        })

    missing_explicit = (
        sorted(set(explicit_dates) - set(observed_dates))
        if explicit_dates is not None else None
    )
    if missing_explicit:
        issues.update(f"expected_observation_missing_{d}" for d in missing_explicit)

    if len(observed_dates) < 2:
        status = "INSUFFICIENT_DISTINCT_DATES"
    elif missing_explicit or any(not day["complete_indicative_source_coverage"] for day in days):
        status = "PARTIAL_OR_INTERRUPTED"
    else:
        status = "MULTI_DATE_INDICATIVE_OBSERVATIONS"

    result = {
        "status": status,
        "distinct_observation_dates": len(observed_dates),
        "total_observations": len(snapshots),
        "observed_dates": observed_dates,
        "expected_dates_source": "explicit_input" if explicit_dates is not None else "not_specified",
        "expected_dates": explicit_dates,
        "missing_expected_dates": missing_explicit,
        "market_holidays_or_weekends_inferred": False,
        "daily_evidence": days,
        "issues": sorted(issues),
        "independent_bist_second_source_verified": False,
        "licensed_non_display_market_data_access_verified": False,
        "long_term_reliability_proven": False,
        "strategy_profitability_inferred": False,
        "research_only": True,
        "prices_executable": False,
        "orders": 0,
        "paper_fills": 0,
        "journal_writes": 0,
        "scheduler_enabled": False,
        "paper_trading_enabled": False,
        "live_trading_enabled": False,
        "network_requests": 0,
    }
    json.dumps(result, allow_nan=False)
    return result


def _no_constants(value: str) -> None:
    raise ValueError("non_finite_json_constant")


def main() -> int:
    p = argparse.ArgumentParser(description="Offline multi-day integrity of explicitly saved observations")
    p.add_argument("--input", type=Path, action="append", required=True,
                   help="Repeat for separate real saved observation JSON artifacts (max 30)")
    p.add_argument("--expected-date", action="append", default=None,
                   help="Only explicit dates are checked for missing observations; no holidays inferred")
    args = p.parse_args()
    try:
        if len(args.input) > MAX_FILES:
            raise ValueError("too_many_observations")
        samples = []
        for path in args.input:
            if path.stat().st_size > MAX_FILE_BYTES:
                raise ValueError("observation_file_too_large")
            samples.append(json.loads(path.read_text(encoding="utf-8"), parse_constant=_no_constants))
        report = summarize_continuity(samples, expected_dates=args.expected_date)
        print(json.dumps(report, ensure_ascii=True, sort_keys=True, allow_nan=False))
        return 0  # Audit succeeded; observations may still be insufficient.
    except (OSError, UnicodeError, TypeError, ValueError) as exc:
        print(json.dumps({
            "status": "BLOCKED", "reason": str(exc)[:120],
            "orders": 0, "live_trading_enabled": False,
        }))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
