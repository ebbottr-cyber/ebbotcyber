"""Manual opt-in, prospective ETF/cash paper observer.

Default mode PREVIEW NEVER WRITES. --commit appends exactly one new daily
record. Not wired to cron, CI schedule, public APIs, brokers or trading tasks.
Requires a durable user-provided journal path on the operating host.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import sys
from pathlib import Path

from src.core.etf_rotation import RotationParams
from src.core.prospective_paper import observe_completed_close
from src.services.prospective_paper_journal import append_paper_record, read_journal


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Read-only ETF prospective paper observer")
    ap.add_argument("--journal", type=Path, required=True,
                    help="Absolute or user-chosen persistent local .jsonl path; parent must exist")
    ap.add_argument("--status", action="store_true", help="Show already recorded results; no network or write")
    ap.add_argument("--commit", action="store_true",
                    help="Opt in to append today's completed session; otherwise dry-run preview")
    ap.add_argument("--asset", default="510300", help="Six-digit A-share ETF identifier")
    ap.add_argument("--lookback", type=int, default=40)
    ap.add_argument("--rebalance", choices=["weekly", "monthly"], default="weekly")
    ap.add_argument("--fee-bps", type=float, default=10.0)
    ap.add_argument("--slippage-bps", type=float, default=5.0)
    ap.add_argument("--history-years", type=int, default=2)
    return ap


def run(args: argparse.Namespace) -> int:
    if args.status and args.commit:
        raise ValueError("--status and --commit are mutually exclusive")
    records = read_journal(args.journal)
    if args.status:
        print(json.dumps({
            "status": "EMPTY" if not records else "PAPER_ONLY",
            "records": len(records),
            "last": records[-1] if records else None,
            "trading_enabled": False,
        }, ensure_ascii=False, allow_nan=False))
        return 0

    if args.history_years not in (1, 2, 3, 4, 5):
        raise ValueError("--history-years must be 1..5")
    params = RotationParams(
        lookback_days=args.lookback,
        rebalance=args.rebalance,
        top_n=1,
        switch_buffer_pct=2.0,
        cost_bps=args.fee_bps,
    )
    from data_provider.base import DataFetcherManager, _is_etf_code
    from src.core.trading_calendar import (
        get_effective_trading_date, get_next_trading_date, get_trading_dates,
    )
    from src.services.etf_rotation_service import data_quality_warnings, load_closes

    if not _is_etf_code(args.asset) or len(args.asset) != 6:
        raise ValueError("prospective research is restricted to recognized six-digit A-share ETFs")

    now = datetime.now(timezone.utc)
    as_of = get_effective_trading_date("cn", current_time=now)
    sessions = get_trading_dates("cn", as_of, as_of)
    if sessions is None or len(sessions) != 1 or sessions[0].date() != as_of:
        raise ValueError("exchange calendar cannot independently verify a completed ETF session")
    next_session = get_next_trading_date("cn", as_of)
    if next_session is None or next_session <= as_of:
        raise ValueError("next session unavailable; cannot freeze prospective signal")

    loaded = load_closes(DataFetcherManager(), [args.asset], years=args.history_years, end=as_of)
    if args.asset in loaded.failed or args.asset not in loaded.closes.columns:
        raise ValueError("forward-adjusted ETF closes unavailable")
    warnings = data_quality_warnings(loaded)
    if warnings:
        raise ValueError("historical price quality warning; paper journal unchanged")

    candidate = observe_completed_close(
        loaded.closes[[args.asset]],
        asset_code=args.asset,
        params=params,
        source=loaded.sources.get(args.asset, ""),
        as_of=as_of,
        next_session=next_session,
        observed_at_utc=now,
        previous=records[-1] if records else None,
        slippage_bps=args.slippage_bps,
    )
    if args.commit:
        append_paper_record(args.journal, candidate)
        status = "RECORDED"
    else:
        status = "PREVIEW_ONLY"
    print(json.dumps({
        "status": status,
        "seq": candidate["seq"],
        "session": candidate["session"],
        "next_session": candidate["next_session"],
        "provider": candidate["source"],
        "signal": candidate["signal"],
        "pending_target": candidate["pending_target"],
        "paper_fill": candidate["fill"],
        "paper_invested": candidate["invested"],
        "equity": candidate["equity"],
        "return_pct": candidate["return_pct"],
        "journal_path": str(args.journal),
        "trading_enabled": False,
    }, ensure_ascii=False, allow_nan=False))
    return 0


def main() -> int:
    args = parser().parse_args()
    try:
        return run(args)
    except Exception as exc:
        print(json.dumps({
            "status": "BLOCKED",
            "error": type(exc).__name__,
            "reason": str(exc)[:220],
            "trading_enabled": False,
        }, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
