# -*- coding: utf-8 -*-
"""BIST100 Yahoo daily OHLCV availability audit (not stock analysis).

Run explicitly with: python -m src.services.bist100_coverage --as-of 2026-11-15
The default operation only queries Yahoo; it never falls back to mainland
providers or claims that collected prices have been analyzed by the bot.
Network I/O is injectable so all automated tests run offline.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
import json
import math
import os
from pathlib import Path
import tempfile
import time
from typing import Callable, Iterable
from zoneinfo import ZoneInfo

import pandas as pd

from src.core.trading_calendar import get_trading_dates
from src.services.bist100_universe import load_bist100_universe

HistoryLoader = Callable[[str, date, date], pd.DataFrame]
CurrencyLoader = Callable[[str], str | None]
_REQUIRED_OHLCV = ("date", "open", "high", "low", "close", "volume")


def _yahoo_daily_history(symbol: str, start: date, end: date) -> pd.DataFrame:
    """Fetch BIST history from the bot's existing yfinance dependency.

    Do not import data_provider here: its eager package initialization pulls
    unrelated mainland-market providers (fake_useragent, efinance, etc.) into
    a BIST-only audit. Yahoo failures still propagate to per-stock fetch_error.
    """
    import yfinance as yf

    # history(..., raise_errors=True) preserves connection / HTTP 429 failures
    # instead of silently returning an empty DataFrame and claiming no_data.
    # The end boundary is exclusive at Yahoo.
    raw = yf.Ticker(symbol).history(
        start=start.isoformat(),
        end=(end + timedelta(days=1)).isoformat(),
        interval="1d",
        auto_adjust=True,
        actions=False,
        raise_errors=True,
    )
    if raw is None or (isinstance(raw, pd.DataFrame) and raw.empty):
        return pd.DataFrame()
    if not isinstance(raw, pd.DataFrame):
        raise TypeError("Yahoo OHLCV response is not a DataFrame")
    frame = raw.copy()
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = frame.columns.get_level_values(0)
    frame = frame.reset_index()
    frame.columns = [str(column).strip().lower() for column in frame.columns]
    return frame


def _yahoo_currency(symbol: str) -> str | None:
    """Read actual provider metadata; never assume a symbol is quoted in TRY."""
    import yfinance as yf

    info = yf.Ticker(symbol).fast_info
    value = info.get("currency") if hasattr(info, "get") else getattr(info, "currency", None)
    return str(value).strip().upper() if value else None


@dataclass(frozen=True)
class StockCoverage:
    symbol: str
    status: str
    rows: int = 0
    first_bar_date: str | None = None
    last_bar_date: str | None = None
    observed_currency: str | None = None
    expected_last_session: str | None = None
    issues: tuple[str, ...] = ()
    error_type: str | None = None


def _validate_history(frame: pd.DataFrame, start: date, as_of: date) -> tuple[pd.DataFrame | None, str | None]:
    if frame is None or (isinstance(frame, pd.DataFrame) and frame.empty):
        return None, "no_data"
    if not isinstance(frame, pd.DataFrame) or any(col not in frame.columns for col in _REQUIRED_OHLCV):
        return None, "invalid_data"

    normalized = frame[list(_REQUIRED_OHLCV)].copy()
    try:
        days = []
        for value in normalized["date"]:
            timestamp = pd.Timestamp(value)
            if pd.isna(timestamp):
                return None, "invalid_data"
            if timestamp.tzinfo is not None:
                timestamp = timestamp.tz_convert("Europe/Istanbul")
            days.append(timestamp.date())
        if len(set(days)) != len(days) or any(day < start or day > as_of for day in days):
            return None, "invalid_data"
        normalized["date"] = days
        for column in _REQUIRED_OHLCV[1:]:
            normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
            if normalized[column].isna().any() or not all(
                math.isfinite(float(v)) for v in normalized[column]
            ):
                return None, "invalid_data"
        if (normalized[["open", "high", "low", "close"]] <= 0).any().any():
            return None, "invalid_data"
        if (normalized["volume"] < 0).any():
            return None, "invalid_data"
        if (
            (normalized["high"] < normalized[["open", "low", "close"]].max(axis=1)).any()
            or (normalized["low"] > normalized[["open", "high", "close"]].min(axis=1)).any()
        ):
            return None, "invalid_data"
        return normalized.sort_values("date").reset_index(drop=True), None
    except (TypeError, ValueError, OverflowError):
        return None, "invalid_data"


def _last_completed_session(as_of: date) -> date | None:
    """Conservatively exclude today's potentially unfinished bar, even after close."""
    try:
        sessions = get_trading_dates("tr", as_of - timedelta(days=45), as_of - timedelta(days=1))
        if sessions is None or len(sessions) == 0:
            return None
        return sessions[-1].date()
    except Exception:  # noqa: BLE001 - unavailable calendar is not a proven session
        return None


def _check_one(
    symbol: str,
    start: date,
    as_of: date,
    last_session: date | None,
    min_bars: int,
    fetch_history: HistoryLoader,
    fetch_currency: CurrencyLoader,
) -> StockCoverage:
    expected = last_session.isoformat() if last_session else None
    try:
        raw = fetch_history(symbol, start, as_of)
    except Exception as exc:  # noqa: BLE001 - one bad symbol must not block the other 99
        return StockCoverage(symbol, "fetch_error", expected_last_session=expected, error_type=type(exc).__name__)
    history, reason = _validate_history(raw, start, as_of)
    if reason:
        return StockCoverage(symbol, reason, expected_last_session=expected)
    assert history is not None
    # The current day's partial bar is not a completed session. Never use it
    # to label a stock as fresh or to satisfy the minimum history threshold.
    cutoff = last_session if last_session else as_of - timedelta(days=1)
    completed = history[history["date"] <= cutoff]
    if completed.empty:
        return StockCoverage(symbol, "no_completed_bars", expected_last_session=expected)
    first = completed["date"].iloc[0].isoformat()
    last = completed["date"].iloc[-1].isoformat()
    issues: list[str] = []
    observed_currency = None
    try:
        currency = fetch_currency(symbol)
        if isinstance(currency, str):
            observed_currency = currency.strip().upper() or None
    except Exception:  # noqa: BLE001 - metadata fetch failures are not price failures
        issues.append("currency_lookup_failed")

    if observed_currency is None:
        issues.append("currency_unverified")
    elif observed_currency != "TRY":
        issues.append("currency_mismatch")
    if last_session is None:
        issues.append("calendar_unavailable")
    elif completed["date"].iloc[-1] < last_session:
        issues.append("stale_price")
    if len(completed) < min_bars:
        issues.append("insufficient_history")

    # Keep every warning, but expose one mutually exclusive primary status.
    for primary in ("currency_mismatch", "stale_price", "insufficient_history",
                    "calendar_unavailable", "currency_unverified"):
        if primary in issues:
            status = primary
            break
    else:
        status = "ready"
    return StockCoverage(
        symbol=symbol, status=status, rows=len(completed),
        first_bar_date=first, last_bar_date=last,
        observed_currency=observed_currency, expected_last_session=expected,
        issues=tuple(issues),
    )


def scan_bist100_history(
    *,
    as_of: date | None = None,
    lookback_days: int = 365,
    min_bars: int = 60,
    symbols: Iterable[str] | None = None,
    fetch_history: HistoryLoader | None = None,
    fetch_currency: CurrencyLoader | None = None,
    delay_seconds: float = 1.5,
) -> dict:
    """Check historical Yahoo coverage without mistaking it for analysis.

    Entire 100-member 2026-Q4 snapshot is selected by default; explicit
    subsets are supported for smoke tests, and reported as INCOMPLETE.
    All statuses are recorded even if network/provider metadata is missing.
    """
    target_day = as_of or datetime.now(ZoneInfo("Europe/Istanbul")).date()
    universe = load_bist100_universe(target_day)
    if lookback_days < 1 or min_bars < 1 or delay_seconds < 0:
        raise ValueError("lookback_days/min_bars must be positive and delay_seconds nonnegative")
    selected = tuple(universe.symbols) if symbols is None else tuple(symbols)
    if len(selected) != len(set(selected)) or any(symbol not in universe.symbols for symbol in selected):
        raise ValueError("Coverage selection must be unique active BIST100 .IS members")
    if not selected:
        raise ValueError("Coverage selection cannot be empty")

    history_loader = fetch_history or _yahoo_daily_history
    currency_loader = fetch_currency or _yahoo_currency
    start = target_day - timedelta(days=lookback_days)
    last_session = _last_completed_session(target_day)
    records = []
    for index, symbol in enumerate(selected):
        if index and delay_seconds:
            time.sleep(delay_seconds)
        records.append(_check_one(
            symbol, start, target_day, last_session, min_bars,
            history_loader, currency_loader,
        ))
    totals = dict(sorted(Counter(item.status for item in records).items()))
    return {
        "index": "BIST100",
        "as_of": target_day.isoformat(),
        "constituent_snapshot_as_of": universe.as_of.isoformat(),
        "constituent_snapshot_effective_to": universe.effective_to.isoformat(),
        "source": "Yahoo Finance",
        "currency_expected": "TRY",
        "calendar": "XIST",
        "timezone": "Europe/Istanbul",
        "expected_last_completed_session": last_session.isoformat() if last_session else None,
        "lookback_days": lookback_days,
        "min_bars": min_bars,
        "universe_total": len(universe.symbols),
        "checked": len(records),
        "remaining": len(universe.symbols) - len(records),
        "complete": len(records) == len(universe.symbols),
        "ready": totals.get("ready", 0),
        "with_valid_price_bars": sum(record.rows > 0 for record in records),
        "status_counts": totals,
        "results": [asdict(record) for record in records],
        "note": "Price coverage only; no stock analysis or orders executed.",
    }


def _write_json_atomically(path: Path, content: str) -> None:
    """Replace the served report only after the full JSON has been written.

    Keep the old valid report readable if serialization or a disk write fails.
    The temporary file is created alongside the target for atomic replacement.
    """
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit BIST100 Yahoo Finance OHLCV coverage")
    parser.add_argument("--as-of", type=date.fromisoformat,
                        default=datetime.now(ZoneInfo("Europe/Istanbul")).date())
    parser.add_argument("--lookback-days", type=int, default=365)
    parser.add_argument("--min-bars", type=int, default=60)
    parser.add_argument("--delay-seconds", type=float, default=1.5)
    parser.add_argument("--limit", type=int, default=None,
                        help="First N stocks for smoke tests; the default is all 100")
    parser.add_argument("--symbols", type=str, default=None,
                        help="Comma-separated active BIST100 Yahoo tickers, e.g. THYAO.IS,ASELS.IS,AKFYE.IS")
    parser.add_argument("--output", type=Path, help="Optional local JSON report file")
    args = parser.parse_args()
    if args.limit is not None and not 1 <= args.limit <= 100:
        parser.error("--limit must be between 1 and 100")
    if args.symbols is not None and args.limit is not None:
        parser.error("--symbols and --limit cannot be combined")
    universe = load_bist100_universe(args.as_of)
    if args.symbols is not None:
        selection = tuple(symbol.strip() for symbol in args.symbols.split(","))
        if not selection or any(symbol not in universe.symbols for symbol in selection):
            parser.error("--symbols must contain canonical active BIST100 .IS tickers")
        if len(selection) != len(set(selection)):
            parser.error("--symbols cannot contain duplicates")
    else:
        selection = universe.symbols[:args.limit] if args.limit is not None else universe.symbols
    report = scan_bist100_history(
        as_of=args.as_of,
        lookback_days=args.lookback_days,
        min_bars=args.min_bars,
        symbols=selection,
        delay_seconds=args.delay_seconds,
    )
    rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output is not None:
        _write_json_atomically(args.output, rendered)
    print(rendered, end="")


if __name__ == "__main__":
    main()
