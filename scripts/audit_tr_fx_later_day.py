"""One-shot manual later-day Turkish market observation vs pinned genuine Nov 20.

CLI defaults to no network. Even --fetch cannot contact providers before a
separate Istanbul calendar day and a weekday, using the process's real clock.
This is NOT an exchange-session calendar: a holiday may still return stale data.
Artifacts are short-lived; no background scheduler, trades, paper fills or
portfolio writes. Never infer a fresh market close from a later fetch timestamp.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime
import json
from pathlib import Path
from typing import Any

from scripts.audit_tr_fx_archived_evidence import (
    PINNED_RUNS, _read_strict_json, validate_archive,
)
from scripts.audit_tr_fx_multiday_continuity import (
    ISTANBUL, _observation_date, summarize_continuity,
)
from scripts.audit_tr_fx_public_sources import summarize as summarize_current

BASELINE = PINNED_RUNS[2]
# Do not infer that a Monday is actually an open Borsa Istanbul session.
MIN_FOLLOWUP_DATE = date(2026, 11, 23)


def load_original_baseline(root: Path) -> tuple[dict, dict]:
    """Verify baseline from original GitHub run, not a copied or fake date."""
    folder = root / str(BASELINE["run_id"])
    meta = _read_strict_json(folder / "run-metadata.json")
    snapshot = _read_strict_json(folder / BASELINE["file"])
    proof = validate_archive(BASELINE, meta, snapshot)
    if proof["observed_local_date"] != "2026-11-20":
        raise ValueError("unexpected_baseline_observation_day")
    return snapshot, proof


def fetch_gate(baseline: dict, now: datetime) -> dict[str, Any]:
    """Pure eligibility decision. Never uses a caller-supplied date in the CLI."""
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("actual_timezone_aware_clock_required")
    original_date_text, original_timestamp = _observation_date(baseline)
    original_date = date.fromisoformat(original_date_text)
    current_day = now.astimezone(ISTANBUL).date()
    permitted = (
        current_day > original_date
        and current_day >= MIN_FOLLOWUP_DATE
        and current_day.weekday() < 5
    )
    return {
        "status": "ELIGIBLE_LATER_WEEKDAY" if permitted else "NOT_ELIGIBLE_YET",
        "baseline_observation_day": original_date.isoformat(),
        "actual_local_day": current_day.isoformat(),
        "earliest_later_weekday": MIN_FOLLOWUP_DATE.isoformat(),
        "market_open_verified": False,
        "market_holidays_inferred": False,
        "user_opt_in_required": True,
        "public_quote_requests_allowed": permitted,
        "network_requests": 0,
        "orders": 0,
        "paper_fills": 0,
        "journal_writes": 0,
        "live_trading_enabled": False,
        "paper_trading_enabled": False,
        "scheduler_enabled": False,
    }


def compare_later_observation(
    baseline: dict, followup: dict, *, now: datetime,
) -> dict[str, Any]:
    """Never accept same-day, future, or repeated publication as new prices."""
    gate = fetch_gate(baseline, now)
    if not gate["public_quote_requests_allowed"]:
        raise ValueError("not_a_later_eligible_weekday")
    before_day, before_timestamp = _observation_date(baseline)
    after_day, after_timestamp = _observation_date(followup)
    if after_day != gate["actual_local_day"]:
        raise ValueError("followup_day_not_actual_local_day")
    if not before_timestamp < after_timestamp:
        raise ValueError("followup_not_after_baseline")
    after_dt = datetime.fromisoformat(after_timestamp)
    # Reject replayed/future-observed snapshots rather than trusting a JSON string.
    if abs((now.astimezone(ISTANBUL) - after_dt).total_seconds()) > 600:
        raise ValueError("followup_not_freshly_observed")
    continuity = summarize_continuity([baseline, followup])
    if continuity["distinct_observation_dates"] != 2:
        raise ValueError("followup_not_distinct_day")
    evidence = {
        key: {
            "progression": item["progression"],
            "actual_publication_dates": item["actual_publication_dates"],
            "distinct_publication_dates": item["distinct_publication_dates"],
            "independent_second_source_verified": False,
        }
        for key, item in continuity["provider_publication_evidence"].items()
    }
    outcome = {
        "status": continuity["status"],
        "baseline_day": before_day,
        "followup_observation_day": after_day,
        "distinct_observation_dates": continuity["distinct_observation_dates"],
        "per_source_publication_evidence": evidence,
        "issues": continuity["issues"],
        "all_provider_publication_dates_advanced": continuity["provider_publication_days_all_advanced"],
        "new_source_day_proven_for_every_source": (
            continuity["provider_publication_days_all_advanced"]
            and continuity["status"] == "MULTI_DATE_INDICATIVE_OBSERVATIONS"
        ),
        "provider_quote_values_repeated_in_report": False,
        "market_open_verified": False,
        "long_term_reliability_proven": False,
        "independent_bist_second_source_verified": False,
        "licensed_non_display_market_data_access_verified": False,
        "research_only": True,
        "prices_executable": False,
        "orders": 0,
        "paper_fills": 0,
        "journal_writes": 0,
        "paper_trading_enabled": False,
        "live_trading_enabled": False,
        "scheduler_enabled": False,
    }
    json.dumps(outcome, allow_nan=False)
    return outcome


def run(baseline: dict, *, now: datetime, fetch: bool = False) -> dict[str, Any]:
    """Only --fetch on a later real weekday calls the two fixed public providers."""
    gate = fetch_gate(baseline, now)
    if not gate["public_quote_requests_allowed"]:
        return gate
    if not fetch:
        return {**gate, "status": "READY_FOR_MANUAL_PUBLIC_DATA_READ", "network_requests": 0}

    # Caller has opted into public source GETs and the clock passed the gate.
    from src.services.tr_market_overview_service import build_overview
    from src.services.tcmb_try_display_service import get_tcmb_try_display_quotes

    try:
        overview = build_overview()
    except Exception:
        overview = {}
    try:
        official = get_tcmb_try_display_quotes(today=now.astimezone(ISTANBUL).date())
    except Exception:
        official = {}
    snapshot = summarize_current(
        overview, official,
        today=now.astimezone(ISTANBUL).date(), observed_at=now,
    )
    return compare_later_observation(baseline, snapshot, now=now)


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only later-day comparison with pinned Nov 20 data")
    parser.add_argument("--baseline-root", type=Path, required=True)
    parser.add_argument("--fetch", action="store_true",
                        help="Explicit one-shot public Yahoo + official TCMB GET; only after 23 Nov")
    args = parser.parse_args()
    try:
        baseline, _ = load_original_baseline(args.baseline_root)
        result = run(baseline, now=datetime.now(ISTANBUL), fetch=args.fetch)
        print(json.dumps(result, ensure_ascii=True, sort_keys=True, allow_nan=False))
        return 0  # Outcome may be NOT_ELIGIBLE_YET or stale/incomplete.
    except (OSError, TypeError, ValueError, KeyError, UnicodeError) as exc:
        print(json.dumps({
            "status": "BLOCKED", "reason": str(exc)[:120],
            "orders": 0, "paper_fills": 0,
            "paper_trading_enabled": False, "live_trading_enabled": False,
        }))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
