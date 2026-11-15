# -*- coding: utf-8 -*-
"""Read-only BIST100 technical ranking over completed, locally persisted OHLCV.

A successful *coverage audit* does not populate SQLite. Run the opt-in
bist100_import command first, then use this screener to reuse the bot's
StockTrendAnalyzer (MA/MACD/RSI/trend/volume/score) without LLM, news,
realtime data, notifications, or trading orders.

The default SQLite connection is file URI mode=ro + PRAGMA query_only=ON.
Never initiate the application's DB migrations merely to screen local bars.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, timedelta
import json
import math
import os
from pathlib import Path
import sqlite3
from typing import Any, Callable, Iterable
from zoneinfo import ZoneInfo

import pandas as pd

from src.services.bist100_coverage import (
    _last_completed_session,
    _validate_history,
    _write_json_atomically,
)
from src.services.bist100_universe import load_bist100_universe

_MIN_TECHNICAL_BARS = 60
_SOURCE = "Yahoo Finance"
_TREND_TR = {
    "STRONG_BULL": "Güçlü yükseliş", "BULL": "Yükseliş",
    "WEAK_BULL": "Zayıf yükseliş", "CONSOLIDATION": "Yatay",
    "WEAK_BEAR": "Zayıf düşüş", "BEAR": "Düşüş",
    "STRONG_BEAR": "Güçlü düşüş",
}
_SIGNAL_TR = {
    "STRONG_BUY": "Güçlü alım sinyali", "BUY": "Alım sinyali",
    "HOLD": "Tut", "WAIT": "İzle", "SELL": "Satış sinyali",
    "STRONG_SELL": "Güçlü satış sinyali",
}


class ReadOnlyStockDaily:
    """Query the existing StockDaily table without creating or editing a DB."""

    def __init__(self, db_path: str | Path):
        location = Path(db_path).expanduser().resolve()
        if not location.is_file():
            raise FileNotFoundError(f"StockDaily database not found: {location}")
        self.location = location
        self.connection = sqlite3.connect(location.as_uri() + "?mode=ro", uri=True)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA query_only=ON")

    def get_data_range(self, code: str, start: date, end: date) -> list[dict]:
        records = self.connection.execute(
            "SELECT date, open, high, low, close, volume, data_source, canonical_id "
            "FROM stock_daily WHERE code=? AND date>=? AND date<=? ORDER BY date",
            (code, start.isoformat(), end.isoformat()),
        ).fetchall()
        return [dict(record) for record in records]

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "ReadOnlyStockDaily":
        return self

    def __exit__(self, *_args) -> None:
        self.close()


def _row_dict(value: Any) -> dict:
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "to_dict"):
        return value.to_dict()
    raise TypeError("StockDaily record has no to_dict representation")


def _finite_number(value: Any) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Technical analysis returned a non-finite number")
    return number


def _screen_one(
    code: str,
    db: Any,
    *,
    first_day: date,
    last_session: date,
    min_bars: int,
    analyze: Callable[[pd.DataFrame, str], Any],
) -> dict:
    result: dict[str, Any] = {"symbol": code, "status": "unavailable"}
    try:
        records = [_row_dict(item) for item in db.get_data_range(code, first_day, last_session)]
    except Exception as exc:  # noqa: BLE001 - never conceal a DB error
        return {**result, "status": "db_error", "error_type": type(exc).__name__}
    if not records:
        return {**result, "status": "not_imported"}

    # Existing stock_daily has no currency column: historical provenance is
    # limited to the canonical .IS ticker and Yahoo-only importer source.
    if any(
        item.get("data_source") != _SOURCE or item.get("canonical_id") != code
        for item in records
    ):
        return {**result, "status": "unverified_source", "bars": len(records)}

    history, problem = _validate_history(
        pd.DataFrame(records), first_day, last_session
    )
    if problem is not None or history is None:
        return {**result, "status": "invalid_data", "bars": len(records)}
    if len(history) < min_bars:
        return {**result, "status": "insufficient_history", "bars": len(history)}
    if history["date"].iloc[-1] != last_session:
        return {
            **result, "status": "stale_price", "bars": len(history),
            "last_bar_date": history["date"].iloc[-1].isoformat(),
        }

    try:
        analyzed = analyze(history, code)
        score = _finite_number(analyzed.signal_score)
        close = _finite_number(analyzed.current_price)
        ma5 = _finite_number(analyzed.ma5)
        ma20 = _finite_number(analyzed.ma20)
        rsi12 = _finite_number(analyzed.rsi_12)
        bias = _finite_number(analyzed.bias_ma5)
        macd = _finite_number(analyzed.macd_bar)
        if not (0 <= score <= 100 and close > 0 and ma5 > 0 and ma20 > 0 and 0 <= rsi12 <= 100):
            raise ValueError("Technical analysis returned values outside safe ranges")
        signal = str(analyzed.buy_signal.name)
        trend = str(analyzed.trend_status.name)
        if signal not in _SIGNAL_TR or trend not in _TREND_TR:
            raise ValueError("Unrecognized technical signal")
    except Exception as exc:  # noqa: BLE001 - exclude bad analysis from the ranking
        return {
            **result, "status": "analysis_error", "bars": len(history),
            "error_type": type(exc).__name__,
        }

    # A large gap above MA5 stays watch-only even when the base analyzer
    # boosts the signal for an unusually strong trend. Not trade advice.
    chase_risk = bias > 5.0
    return {
        "symbol": code, "status": "analyzed", "bars": len(history),
        "last_bar_date": last_session.isoformat(), "score": int(score),
        "close_try": round(close, 4), "ma5_try": round(ma5, 4),
        "ma20_try": round(ma20, 4), "rsi12": round(rsi12, 2),
        "macd_histogram": round(macd, 4), "bias_ma5_pct": round(bias, 2),
        "trend": _TREND_TR[trend], "technical_signal": _SIGNAL_TR[signal],
        "chase_risk": chase_risk,
        "eligible_for_watchlist": not chase_risk,
    }


def screen_bist100_from_db(
    *,
    as_of: date,
    symbols: Iterable[str] | None = None,
    min_bars: int = _MIN_TECHNICAL_BARS,
    lookback_days: int = 365,
    db: Any | None = None,
    analyze: Callable[[pd.DataFrame, str], Any] | None = None,
    db_path: str | Path | None = None,
    last_session: date | None = None,
) -> dict:
    """Rank only valid current members with fresh complete bars.

    All 100 members are checked by default; failed/missing members are visible
    in results but do NOT participate in ranking. No network or trade action.
    """
    universe = load_bist100_universe(as_of)
    selection = tuple(universe.symbols if symbols is None else symbols)
    if min_bars < _MIN_TECHNICAL_BARS or lookback_days < min_bars * 2:
        raise ValueError("At least 60 bars and enough calendar lookback are required")
    if not selection or len(selection) != len(set(selection)) or any(
        stock not in universe.symbols for stock in selection
    ):
        raise ValueError("Select unique active canonical BIST100 .IS stocks")

    cutoff = last_session if last_session is not None else _last_completed_session(as_of)
    if cutoff is None or cutoff >= as_of:
        raise ValueError("No verified completed XIST session: refusing to rank")
    start = as_of - timedelta(days=lookback_days)

    if analyze is None:
        # Reuse the bot's existing tested technical engine; load lazily to
        # keep raw DB quality validation available to lightweight callers.
        from src.stock_analyzer import StockTrendAnalyzer
        analyze = StockTrendAnalyzer().analyze

    owns_db = db is None
    if owns_db:
        configured = db_path or os.getenv("DATABASE_PATH", "./data/stock_analysis.db")
        db = ReadOnlyStockDaily(configured)
    try:
        records = [
            _screen_one(code, db, first_day=start, last_session=cutoff,
                        min_bars=min_bars, analyze=analyze)
            for code in selection
        ]
    finally:
        if owns_db:
            db.close()

    # Score ties resolve by ticker, never by fetch order. Watch-only risk
    # stocks can be ranked, but may not be silently promoted to a buy list.
    ranked = sorted(
        (dict(row) for row in records if row["status"] == "analyzed"),
        key=lambda row: (-row["score"], row["symbol"]),
    )
    for index, row in enumerate(ranked, start=1):
        row["rank"] = index
    status_counts = dict(sorted(Counter(row["status"] for row in records).items()))
    return {
        "index": "BIST100", "as_of": as_of.isoformat(),
        "last_completed_session": cutoff.isoformat(),
        "mode": "read_only_local_sqlite",
        "universe_total": len(universe.symbols), "checked": len(selection),
        "remaining": len(universe.symbols) - len(selection),
        "analyzed": len(ranked), "status_counts": status_counts,
        "watchlist_eligible": sum(row["eligible_for_watchlist"] for row in ranked),
        "ranking": ranked, "results": records,
        "note": "Historical technical ranking only. No LLM, trades, or investment recommendation.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read-only BIST100 technical ranking from existing StockDaily SQLite"
    )
    parser.add_argument("--as-of", type=date.fromisoformat,
                        default=datetime.now(ZoneInfo("Europe/Istanbul")).date())
    parser.add_argument("--symbols", type=str, help="Comma-separated canonical BIST100 tickers")
    parser.add_argument("--limit", type=int, help="First 1..100 stocks, for a smoke test")
    parser.add_argument("--db-path", type=Path, help="Existing StockDaily SQLite file")
    parser.add_argument("--min-bars", type=int, default=_MIN_TECHNICAL_BARS)
    parser.add_argument("--lookback-days", type=int, default=365)
    parser.add_argument("--output", type=Path, help="Optional local JSON output file")
    args = parser.parse_args()
    if args.limit is not None and not 1 <= args.limit <= 100:
        parser.error("--limit must be 1..100")
    if args.symbols is not None and args.limit is not None:
        parser.error("--limit and --symbols cannot be combined")
    try:
        universe = load_bist100_universe(args.as_of)
        selection = (
            tuple(x.strip() for x in args.symbols.split(","))
            if args.symbols is not None
            else universe.symbols[:args.limit] if args.limit is not None else universe.symbols
        )
        report = screen_bist100_from_db(
            as_of=args.as_of, symbols=selection,
            db_path=args.db_path, min_bars=args.min_bars,
            lookback_days=args.lookback_days,
        )
    except (ValueError, FileNotFoundError, sqlite3.DatabaseError) as exc:
        parser.error(str(exc))
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        _write_json_atomically(args.output, rendered)
    print(rendered, end="")


if __name__ == "__main__":
    main()
