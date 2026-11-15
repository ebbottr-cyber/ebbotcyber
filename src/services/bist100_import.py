# -*- coding: utf-8 -*-
"""Explicit, opt-in Yahoo BIST100 daily-history import into the bot's StockDaily DB.

The 100/100 coverage JSON records status, not OHLCV rows. This command
downloads the actual bars again and, only with --write-db, upserts them
via the *existing* src.storage DatabaseManager. No analysis, orders or
other-market provider fallbacks are invoked.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, timedelta
import json
import time
from typing import Any, Callable, Iterable
from zoneinfo import ZoneInfo

import pandas as pd

from src.services.bist100_coverage import (
    _check_one,
    _last_completed_session,
    _validate_history,
    _yahoo_currency,
    _yahoo_daily_history,
)
from src.services.bist100_universe import load_bist100_universe


def _prepare_for_storage(history: pd.DataFrame, last_session: date) -> pd.DataFrame:
    """Store only finished sessions and calculate indicators from real closes."""
    complete = history.loc[history["date"] <= last_session].copy()
    if complete.empty:
        raise ValueError("No completed BIST session bars to store")
    complete = complete.sort_values("date").reset_index(drop=True)
    close = complete["close"].astype(float)
    # These columns mirror the existing StockDaily schema. Unknown turnover
    # and intraday volume ratio are intentionally left NULL (not fabricated).
    for days in (5, 10, 20):
        complete[f"ma{days}"] = close.rolling(days, min_periods=days).mean()
    complete["pct_chg"] = close.pct_change() * 100
    return complete


def import_bist100_history(
    *,
    as_of: date,
    symbols: Iterable[str] | None = None,
    lookback_days: int = 365,
    min_bars: int = 60,
    delay_seconds: float = 1.5,
    write_db: bool = False,
    db: Any | None = None,
    fetch_history: Callable[[str, date, date], pd.DataFrame] | None = None,
    fetch_currency: Callable[[str], str | None] | None = None,
) -> dict:
    """Validate provider data and optionally persist it in the bot's DB.

    A write is *never* implicit; even a provided DB object is not written
    unless write_db=True. Exceptions for individual stocks remain visible.
    """
    universe = load_bist100_universe(as_of)
    if lookback_days < 1 or min_bars < 1 or delay_seconds < 0:
        raise ValueError("lookback_days/min_bars must be positive and delay nonnegative")
    selected = tuple(universe.symbols if symbols is None else symbols)
    if not selected or len(selected) != len(set(selected)) or any(
        name not in universe.symbols for name in selected
    ):
        raise ValueError("Selection must contain unique active BIST100 .IS equity symbols")

    if write_db and db is None:
        # Lazy import: a read-only inspection needs only pandas/yfinance, not
        # the whole analysis runtime or a configured database.
        from src.storage import get_db
        db = get_db()
    if write_db and not all(
        callable(getattr(db, method, None))
        for method in ("save_daily_data", "get_data_range")
    ):
        raise ValueError("An initialized StockDaily database writer/reader is required")

    last_session = _last_completed_session(as_of)
    start = as_of - timedelta(days=lookback_days)
    history_loader = fetch_history or _yahoo_daily_history
    currency_loader = fetch_currency or _yahoo_currency
    entries: list[dict] = []
    for index, symbol in enumerate(selected):
        if index and delay_seconds:
            time.sleep(delay_seconds)
        captured: dict[str, pd.DataFrame] = {}

        def capture_history(stock: str, begin: date, end: date) -> pd.DataFrame:
            frame = history_loader(stock, begin, end)
            captured["frame"] = frame
            return frame

        coverage = _check_one(
            symbol, start, as_of, last_session, min_bars,
            capture_history, currency_loader,
        )
        entry = {
            "symbol": symbol,
            "coverage_status": coverage.status,
            "rows": coverage.rows,
            "last_bar_date": coverage.last_bar_date,
            "storage_status": "not_eligible" if coverage.status != "ready" else "dry_run",
            "new_rows": 0,
        }
        if coverage.error_type:
            entry["error_type"] = coverage.error_type

        if coverage.status == "ready" and write_db:
            try:
                assert last_session is not None
                checked, error = _validate_history(captured["frame"], start, as_of)
                if error or checked is None:
                    raise ValueError(f"History invalidated before import: {error}")
                completed = _prepare_for_storage(checked, last_session)
                inserted = db.save_daily_data(
                    completed, symbol, "Yahoo Finance", canonical_id=symbol,
                )
                # save_daily_data returns newly inserted, not updated, rows.
                # Verify the actual stored dates rather than treating 0 as an error.
                stored = db.get_data_range(symbol, start, last_session)
                stored_dates = {bar.date for bar in stored}
                expected_dates = set(completed["date"].tolist())
                if not expected_dates.issubset(stored_dates):
                    raise RuntimeError("StockDaily read-back is missing imported sessions")
                entry["storage_status"] = "imported"
                entry["new_rows"] = int(inserted)
            except Exception as exc:  # one DB failure must not disguise other stocks
                entry["storage_status"] = "db_error"
                entry["error_type"] = type(exc).__name__

        entries.append(entry)
    statuses = dict(sorted(Counter(x["coverage_status"] for x in entries).items()))
    storage_statuses = dict(sorted(Counter(x["storage_status"] for x in entries).items()))
    return {
        "index": "BIST100",
        "as_of": as_of.isoformat(),
        "last_completed_session": last_session.isoformat() if last_session else None,
        "mode": "write_db" if write_db else "dry_run",
        "database": "existing StockDaily" if write_db else "not opened",
        "checked": len(entries),
        "ready_for_import": statuses.get("ready", 0),
        "imported": storage_statuses.get("imported", 0),
        "new_rows": sum(x["new_rows"] for x in entries),
        "coverage_status_counts": statuses,
        "storage_status_counts": storage_statuses,
        "results": entries,
        "note": "Daily OHLCV storage only; no AI analysis, notification, or orders.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="BIST100 Yahoo historical bars -> existing StockDaily DB (opt-in)"
    )
    parser.add_argument("--as-of", type=date.fromisoformat, default=None,
                        help="2026-Q4 snapshot date, e.g. 2026-11-15")
    parser.add_argument("--symbols", help="Comma-separated active .IS equity symbols")
    parser.add_argument("--limit", type=int, help="First N members; 1..100")
    parser.add_argument("--lookback-days", type=int, default=365)
    parser.add_argument("--min-bars", type=int, default=60)
    parser.add_argument("--delay-seconds", type=float, default=1.5)
    parser.add_argument("--write-db", action="store_true",
                        help="Explicitly upsert into the configured DATABASE_PATH")
    args = parser.parse_args()
    if args.limit is not None and not 1 <= args.limit <= 100:
        parser.error("--limit must be 1..100")
    if args.symbols is not None and args.limit is not None:
        parser.error("--limit and --symbols are mutually exclusive")
    as_of = args.as_of or datetime.now(ZoneInfo("Europe/Istanbul")).date()
    universe = load_bist100_universe(as_of)
    if args.symbols:
        selected = tuple(part.strip() for part in args.symbols.split(","))
    elif args.symbols is not None:
        parser.error("--symbols cannot be empty")
    else:
        selected = universe.symbols[:args.limit] if args.limit is not None else universe.symbols
    if not selected or len(selected) != len(set(selected)) or any(
        symbol not in universe.symbols for symbol in selected
    ):
        parser.error("--symbols must contain unique current BIST100 .IS stocks")
    report = import_bist100_history(
        as_of=as_of,
        symbols=selected,
        lookback_days=args.lookback_days,
        min_bars=args.min_bars,
        delay_seconds=args.delay_seconds,
        write_db=args.write_db,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
