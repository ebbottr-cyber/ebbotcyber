# -*- coding: utf-8 -*-
"""Read-only real Yahoo OHLCV + existing technical analyzer smoke for six markets.

This is a *one-symbol-per-market* provider fallback smoke, not proof that a
market's complete symbol universe, prioritized provider routing, or AI reports
are production ready. No SQLite, LLM, signals dispatch, or orders are used.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import json
import math
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

import pandas as pd

from src.core.trading_calendar import get_market_for_stock, get_trading_dates, MARKET_TIMEZONE
from src.stock_analyzer import StockTrendAnalyzer


@dataclass(frozen=True)
class MarketProbe:
    market: str
    code: str
    yahoo: str
    currency: str


# Six symbols are smoke examples, not constituent lists or price recommendations.
PROBES = (
    MarketProbe("cn", "600519", "600519.SS", "CNY"),
    MarketProbe("hk", "HK00700", "0700.HK", "HKD"),
    MarketProbe("us", "AAPL", "AAPL", "USD"),
    MarketProbe("jp", "7203.T", "7203.T", "JPY"),
    MarketProbe("kr", "005930.KS", "005930.KS", "KRW"),
    MarketProbe("tw", "2330.TW", "2330.TW", "TWD"),
)


def _fetch_yahoo_history(symbol: str, start: date, as_of: date) -> pd.DataFrame:
    import yfinance as yf

    raw = yf.Ticker(symbol).history(
        start=start.isoformat(),
        end=(as_of + timedelta(days=1)).isoformat(),
        interval="1d",
        auto_adjust=True,
        actions=False,
        raise_errors=True,
    )
    if not isinstance(raw, pd.DataFrame):
        raise TypeError("Yahoo response is not tabular")
    return raw


def _fetch_yahoo_currency(symbol: str) -> str | None:
    import yfinance as yf

    info = yf.Ticker(symbol).fast_info
    value = info.get("currency") if hasattr(info, "get") else getattr(info, "currency", None)
    return str(value).strip().upper() if value else None


def _to_ohlcv(raw: pd.DataFrame, *, market: str, start: date, last: date) -> pd.DataFrame:
    if not isinstance(raw, pd.DataFrame) or raw.empty:
        raise ValueError("no_data")
    frame = raw.copy()
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = frame.columns.get_level_values(0)
    if "date" not in frame.columns and "Date" not in frame.columns:
        frame = frame.reset_index()
    frame.columns = [str(c).strip().lower() for c in frame.columns]
    needed = ("date", "open", "high", "low", "close", "volume")
    if any(col not in frame.columns for col in needed):
        raise ValueError("invalid_data")
    frame = frame[list(needed)].copy()
    try:
        days = []
        for value in frame["date"]:
            timestamp = pd.Timestamp(value)
            if pd.isna(timestamp):
                raise ValueError("invalid_data")
            if timestamp.tzinfo is not None:
                timestamp = timestamp.tz_convert(MARKET_TIMEZONE[market])
            days.append(timestamp.date())
        frame["date"] = days
        if len(set(days)) != len(days):
            raise ValueError("invalid_data")
        if any(day < start or day > last for day in days):
            raise ValueError("incomplete_or_future_data")
        for key in needed[1:]:
            frame[key] = pd.to_numeric(frame[key], errors="coerce")
            if frame[key].isna().any() or not all(math.isfinite(float(x)) for x in frame[key]):
                raise ValueError("invalid_data")
        if (frame[["open", "high", "low", "close"]] <= 0).any().any():
            raise ValueError("invalid_data")
        if (frame["volume"] < 0).any():
            raise ValueError("invalid_data")
        if (
            (frame["high"] < frame[["open", "close", "low"]].max(axis=1)).any()
            or (frame["low"] > frame[["open", "close", "high"]].min(axis=1)).any()
        ):
            raise ValueError("invalid_data")
        return frame.sort_values("date").reset_index(drop=True)
    except (TypeError, OverflowError) as exc:
        raise ValueError("invalid_data") from exc


def probe_six_markets(
    *,
    as_of: date,
    lookback_days: int = 365,
    min_bars: int = 60,
    fetch_history: Callable[[str, date, date], pd.DataFrame] = _fetch_yahoo_history,
    fetch_currency: Callable[[str], str | None] = _fetch_yahoo_currency,
    sessions_for_market: Callable[[str, date, date], Any] = get_trading_dates,
    detect_market: Callable[[str], str | None] = get_market_for_stock,
    convert_ticker: Callable[[str], str] | None = None,
    analyzer: Callable[[pd.DataFrame, str], Any] | None = None,
    probes: tuple[MarketProbe, ...] = PROBES,
    scope: str = "six_market_yahoo_fallback_one_symbol_each",
) -> dict:
    if lookback_days < min_bars * 2 or min_bars < 60:
        raise ValueError("Need >=60 daily bars and sufficient calendar lookback")
    if convert_ticker is None:
        from data_provider.yfinance_fetcher import YfinanceFetcher
        convert_ticker = YfinanceFetcher()._convert_stock_code
    if analyzer is None:
        analyzer = StockTrendAnalyzer().analyze

    start = as_of - timedelta(days=lookback_days)
    results: list[dict[str, Any]] = []
    for spec in probes:
        item: dict[str, Any] = {
            "market": spec.market, "code": spec.code, "yahoo_symbol": spec.yahoo,
            "currency_expected": spec.currency, "status": "unavailable",
        }
        try:
            actual_market = detect_market(spec.code)
            actual_yahoo = convert_ticker(spec.code)
            if actual_market != spec.market or actual_yahoo != spec.yahoo:
                item.update(status="routing_mismatch", actual_market=actual_market, actual_yahoo=actual_yahoo)
                results.append(item)
                continue
        except Exception as exc:
            item.update(status="routing_error", error_type=type(exc).__name__)
            results.append(item)
            continue

        try:
            sessions = sessions_for_market(spec.market, as_of - timedelta(days=20), as_of - timedelta(days=1))
            if sessions is None or len(sessions) == 0:
                item["status"] = "calendar_unavailable"
                results.append(item)
                continue
            last = pd.Timestamp(sessions[-1]).date()
            item["expected_last_session"] = last.isoformat()
        except Exception:
            item["status"] = "calendar_unavailable"
            results.append(item)
            continue

        try:
            raw = fetch_history(spec.yahoo, start, as_of)
        except Exception as exc:
            item.update(status="fetch_error", error_type=type(exc).__name__)
            results.append(item)
            continue
        try:
            frame = _to_ohlcv(raw, market=spec.market, start=start, last=last)
            item["bars"] = len(frame)
            item["last_bar_date"] = frame["date"].iloc[-1].isoformat()
            if len(frame) < min_bars:
                item["status"] = "insufficient_history"
                results.append(item)
                continue
            if frame["date"].iloc[-1] != last:
                item["status"] = "stale_price"
                results.append(item)
                continue
        except ValueError as exc:
            item["status"] = str(exc) if str(exc) in {
                "no_data", "invalid_data", "incomplete_or_future_data"
            } else "invalid_data"
            results.append(item)
            continue

        try:
            observed = fetch_currency(spec.yahoo)
            item["currency_observed"] = observed
        except Exception:
            item["currency_observed"] = None
        if item["currency_observed"] is None:
            item["status"] = "currency_unverified"
            results.append(item)
            continue
        if item["currency_observed"] != spec.currency:
            item["status"] = "currency_mismatch"
            results.append(item)
            continue
        try:
            analysis = analyzer(frame, spec.code)
            score = float(analysis.signal_score)
            if not math.isfinite(score) or not 0 <= score <= 100:
                raise ValueError("Invalid score")
            item.update(status="analyzed", technical_score=int(score))
        except Exception as exc:
            item.update(status="analysis_error", error_type=type(exc).__name__)
        results.append(item)

    return {
        "scope": scope,
        "as_of": as_of.isoformat(), "source": "Yahoo Finance",
        "checked_markets": len(results),
        "analyzed_markets": sum(x["status"] == "analyzed" for x in results),
        "results": results,
        "note": "Provider fallback/technical smoke only; not full provider routing, AI analysis, or trading.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only six-market Yahoo historical/technical smoke")
    parser.add_argument("--as-of", type=date.fromisoformat,
                        default=datetime.now(ZoneInfo("Europe/Istanbul")).date())
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = probe_six_markets(as_of=args.as_of)
    content = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(content, encoding="utf-8")
    print(content, end="")
    if report["analyzed_markets"] != 6:
        raise SystemExit("Six-market provider smoke incomplete: inspect JSON statuses")


if __name__ == "__main__":
    main()
