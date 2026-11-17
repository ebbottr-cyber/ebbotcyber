"""CoinGecko market-cap Top 100 and on-demand Daily technical strategy checks.

Read only. CoinGecko ID (not symbol) is the identity; no stock list writes.
"""
from __future__ import annotations
import math
import os
import re
import threading
import time
from datetime import datetime, timezone
from typing import Any
import pandas as pd
import requests
from src.stock_analyzer import StockTrendAnalyzer

BASE_URL = "https://api.coingecko.com/api/v3"
COIN_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,119}$")
_lock = threading.RLock()
_roster: dict[str, Any] | None = None
_roster_time = 0.0
_technical_cache: dict[str, tuple[float, dict[str, Any]]] = {}


class CoinGeckoError(RuntimeError):
    pass


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def _fetch(path: str, params: dict[str, Any]) -> Any:
    headers = {"Accept": "application/json", "User-Agent": "ETRE-Top100/1.0"}
    key = os.getenv("COINGECKO_DEMO_API_KEY", "").strip()
    if key:
        headers["x-cg-demo-api-key"] = key
    try:
        response = requests.get(BASE_URL + path, params=params, headers=headers, timeout=(4, 12))
        if response.status_code == 429:
            raise CoinGeckoError("rate_limited")
        if response.status_code in (401, 403):
            raise CoinGeckoError("access_denied")
        response.raise_for_status()
        return response.json()
    except CoinGeckoError:
        raise
    except (requests.RequestException, ValueError) as exc:
        raise CoinGeckoError("unavailable") from exc


def _normalize_roster(data: Any) -> dict[str, Any]:
    if not isinstance(data, list) or len(data) != 100:
        raise CoinGeckoError("invalid_top100")
    coins, seen = [], set()
    for raw in data:
        if not isinstance(raw, dict):
            raise CoinGeckoError("invalid_top100")
        cid, symbol, name = raw.get("id"), raw.get("symbol"), raw.get("name")
        if (not isinstance(cid, str) or not COIN_ID.fullmatch(cid) or cid in seen
                or not isinstance(symbol, str) or not symbol.strip()
                or not isinstance(name, str) or not name.strip()):
            raise CoinGeckoError("invalid_top100")
        seen.add(cid)
        coins.append({
            "id": cid, "symbol": symbol.upper(), "name": name,
            "market_cap_rank": raw.get("market_cap_rank") if type(raw.get("market_cap_rank")) is int else None,
            "current_price": _number(raw.get("current_price")),
            "market_cap": _number(raw.get("market_cap")),
            "total_volume": _number(raw.get("total_volume")),
            "price_change_percentage_24h": _number(raw.get("price_change_percentage_24h")),
        })
    return {
        "source": "CoinGecko", "market": "crypto", "vs_currency": "usd",
        "count": 100, "target_count": 100,
        "as_of": datetime.now(timezone.utc).isoformat(), "coins": coins,
    }


def top100() -> dict[str, Any]:
    global _roster, _roster_time
    with _lock:
        now = time.monotonic()
        if _roster and now - _roster_time < 600:
            return {**_roster, "cached": True, "stale": False}
        try:
            result = _normalize_roster(_fetch("/coins/markets", {
                "vs_currency": "usd", "order": "market_cap_desc", "per_page": 100,
                "page": 1, "sparkline": "false", "locale": "en",
            }))
        except CoinGeckoError:
            if _roster and now - _roster_time < 21600:
                return {**_roster, "cached": True, "stale": True}
            raise
        _roster, _roster_time = result, time.monotonic()
        return {**result, "cached": False, "stale": False}


def _utc_day(ms: Any) -> str | None:
    try:
        if isinstance(ms, bool):
            return None
        number = float(ms)
        if number <= 0 or not math.isfinite(number):
            return None
        return datetime.fromtimestamp(number / 1000, tz=timezone.utc).date().isoformat()
    except (ValueError, TypeError, OSError, OverflowError):
        return None


def daily_bars(ohlc: Any, chart: Any) -> pd.DataFrame:
    """Genuine OHLC aggregation by completed UTC date; rolling 24h volume proxy."""
    if not isinstance(ohlc, list) or not isinstance(chart, dict):
        raise CoinGeckoError("invalid_history")
    today = datetime.now(timezone.utc).date().isoformat()
    candles: dict[str, dict[str, Any]] = {}
    for bar in ohlc:
        if not isinstance(bar, list) or len(bar) != 5:
            continue
        day, numbers = _utc_day(bar[0]), [_number(v) for v in bar[1:]]
        if day is None or day >= today or any(v is None or v <= 0 for v in numbers):
            continue
        opening, high, low, closing = numbers
        if high < max(opening, closing) or low > min(opening, closing):
            continue
        if day not in candles:
            candles[day] = {"date": day, "open": opening, "high": high, "low": low, "close": closing}
        else:
            previous = candles[day]
            previous["high"] = max(previous["high"], high)
            previous["low"] = min(previous["low"], low)
            previous["close"] = closing
    volumes: dict[str, tuple[float, float]] = {}
    samples = chart.get("total_volumes")
    if not isinstance(samples, list):
        raise CoinGeckoError("invalid_history")
    for sample in samples:
        if not isinstance(sample, list) or len(sample) != 2:
            continue
        day, volume = _utc_day(sample[0]), _number(sample[1])
        if day is None or volume is None or volume <= 0:
            continue
        ts = float(sample[0])
        if day not in volumes or ts > volumes[day][0]:
            volumes[day] = (ts, volume)
    data = [{**candles[day], "volume": volumes[day][1]} for day in sorted(candles) if day in volumes]
    if len(data) < 26:
        raise CoinGeckoError("insufficient_history")
    return pd.DataFrame(data)


def analyze_coin(coin_id: str) -> dict[str, Any]:
    if not COIN_ID.fullmatch(coin_id):
        raise CoinGeckoError("unknown_coin")
    coin = next((item for item in top100()["coins"] if item["id"] == coin_id), None)
    if coin is None:
        raise CoinGeckoError("unknown_coin")
    with _lock:
        cached = _technical_cache.get(coin_id)
        if cached and time.monotonic() - cached[0] < 900:
            return {**cached[1], "cached": True}
    ohlc = _fetch("/coins/" + coin_id + "/ohlc", {"vs_currency": "usd", "days": 30})
    chart = _fetch("/coins/" + coin_id + "/market_chart", {"vs_currency": "usd", "days": 30})
    bars = daily_bars(ohlc, chart)
    result = StockTrendAnalyzer().analyze(bars, coin_id)
    payload = {
        "coin": {"id": coin["id"], "name": coin["name"], "symbol": coin["symbol"]},
        "source": "CoinGecko", "strategy": "Daily StockTrendAnalyzer",
        "as_of": datetime.now(timezone.utc).isoformat(),
        "last_completed_day": str(bars.iloc[-1]["date"]), "daily_bars": len(bars),
        "score": result.signal_score, "signal": result.buy_signal.name.lower(),
        "trend": result.trend_status.name.lower(), "macd_status": result.macd_status.name.lower(),
        "rsi_status": result.rsi_status.name.lower(), "rsi_12": result.rsi_12,
        "ma5": result.ma5, "ma10": result.ma10, "ma20": result.ma20,
        "bias_ma5": result.bias_ma5, "volume_ratio_5d": result.volume_ratio_5d,
        "support_levels": result.support_levels, "resistance_levels": result.resistance_levels,
        "cached": False,
        "limitations": [
            "Only 30 days of CoinGecko OHLC aggregated into completed UTC daily candles.",
            "Volume uses rolling 24h USD volume close to day end, not exchange daily volume.",
            "Equity strategy thresholds are uncalibrated for crypto; MA60 falls back to MA20.",
            "Research only: no orders, promises, or automatic 100-coin scanning.",
        ],
    }
    with _lock:
        if len(_technical_cache) >= 100:
            _technical_cache.clear()
        _technical_cache[coin_id] = (time.monotonic(), payload)
    return payload
