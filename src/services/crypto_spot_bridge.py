"""Read-only Spot market-data gateway to the isolated Trading Office.

Strict response contracts, bounded HTTP reads, stale-data rejection, tiny in-memory
TTL cache. No credentials beyond server-side READ_API_KEY; never place orders.
Trading Office owns Binance/CCXT, retry and per-market circuit breaker logic.
"""
from __future__ import annotations

import json
import math
import re
import threading
import time
from datetime import datetime, timezone
from typing import Any, Literal

import httpx

from src.services.crypto_office_bridge import _connection_settings

Dataset = Literal["ticker", "ohlcv", "orderbook"]
TIMEFRAMES = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}
SYMBOL_PATTERN = re.compile(r"^[A-Z0-9]{2,20}/(?:USDT|USDC|BTC|ETH)$")
CACHE_TTLS = {"ticker": 6.0, "ohlcv": 30.0, "orderbook": 5.0}
MAX_BODY_SIZE = 350_000
_CACHE: dict[tuple, tuple[float, dict[str, Any]]] = {}
_LOCK = threading.RLock()


class SpotDataError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _number(value: Any, *, positive: bool = False, nonnegative: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SpotDataError("invalid_market_data")
    parsed = float(value)
    if not math.isfinite(parsed) or positive and parsed <= 0 or nonnegative and parsed < 0:
        raise SpotDataError("invalid_market_data")
    return parsed


def _optional(value: Any, *, positive: bool = False, nonnegative: bool = False) -> float | None:
    return None if value is None else _number(value, positive=positive, nonnegative=nonnegative)


def _timestamp(value: Any, *, required: bool = False) -> int | None:
    if value is None and not required:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise SpotDataError("invalid_market_data")
    if value > (time.time() + 300) * 1000:
        raise SpotDataError("future_market_data")
    return value


def _freshness(stamp: int | None, *, max_age_seconds: float) -> str:
    if stamp is None:
        return "unknown"
    if time.time() * 1000 - stamp > max_age_seconds * 1000:
        raise SpotDataError("stale_market_data")
    return "ok"


def _common(raw: Any, symbol: str, dataset: Dataset) -> dict:
    if not isinstance(raw, dict) or raw.get("market") != "spot" or raw.get("symbol") != symbol:
        raise SpotDataError("wrong_market_identity")
    if raw.get("source") not in {"Binance public market data", "Binance public order book"}:
        raise SpotDataError("wrong_market_identity")
    if dataset == "orderbook" and raw["source"] != "Binance public order book":
        raise SpotDataError("wrong_market_identity")
    if dataset != "orderbook" and raw["source"] != "Binance public market data":
        raise SpotDataError("wrong_market_identity")
    return {
        "market": "spot",
        "symbol": symbol,
        "provider": "Binance",
        "source": raw["source"],
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "orders_enabled": False,
    }


def validate_ticker(raw: Any, symbol: str) -> dict:
    result = _common(raw, symbol, "ticker")
    last = _number(raw.get("last"), positive=True)
    bid = _optional(raw.get("bid"), positive=True)
    ask = _optional(raw.get("ask"), positive=True)
    if bid is not None and ask is not None and bid > ask:
        raise SpotDataError("invalid_market_data")
    high = _optional(raw.get("high_24h"), positive=True)
    low = _optional(raw.get("low_24h"), positive=True)
    if high is not None and low is not None and high < low:
        raise SpotDataError("invalid_market_data")
    stamp = _timestamp(raw.get("timestamp"))
    result.update({
        "last": last, "bid": bid, "ask": ask, "high_24h": high, "low_24h": low,
        "base_volume_24h": _optional(raw.get("base_volume_24h"), nonnegative=True),
        "quote_volume_24h": _optional(raw.get("quote_volume_24h"), nonnegative=True),
        "timestamp": stamp,
        "quality": _freshness(stamp, max_age_seconds=180),
    })
    return result


def validate_ohlcv(raw: Any, symbol: str, timeframe: str, limit: int) -> dict:
    result = _common(raw, symbol, "ohlcv")
    if raw.get("timeframe") != timeframe:
        raise SpotDataError("wrong_market_identity")
    candles = raw.get("candles")
    if not isinstance(candles, list) or not candles or len(candles) > limit or raw.get("count") != len(candles):
        raise SpotDataError("invalid_market_data")
    normalized = []
    previous = 0
    for candle in candles:
        if not isinstance(candle, dict):
            raise SpotDataError("invalid_market_data")
        stamp = _timestamp(candle.get("timestamp"), required=True)
        if stamp is None or stamp <= previous:
            raise SpotDataError("invalid_market_data")
        previous = stamp
        opening = _number(candle.get("open"), positive=True)
        high = _number(candle.get("high"), positive=True)
        low = _number(candle.get("low"), positive=True)
        closing = _number(candle.get("close"), positive=True)
        volume = _number(candle.get("volume"), nonnegative=True)
        if high < max(opening, low, closing) or low > min(opening, high, closing):
            raise SpotDataError("invalid_market_data")
        normalized.append({
            "timestamp": stamp, "open": opening, "high": high,
            "low": low, "close": closing, "volume": volume,
        })
    # For crypto markets (24/7), candles that are >3 intervals old cannot
    # be treated as fresh inputs for an active Spot analysis.
    quality = _freshness(previous, max_age_seconds=TIMEFRAMES[timeframe] * 3 + 180)
    result.update({"timeframe": timeframe, "count": len(normalized), "candles": normalized,
                   "last_candle_timestamp": previous, "quality": quality})
    return result


def validate_orderbook(raw: Any, symbol: str, limit: int) -> dict:
    result = _common(raw, symbol, "orderbook")
    parsed: dict[str, list[list[float]]] = {}
    for side in ("bids", "asks"):
        levels = raw.get(side)
        if not isinstance(levels, list) or not levels or len(levels) > limit:
            raise SpotDataError("invalid_market_data")
        rows: list[list[float]] = []
        for level in levels:
            if not isinstance(level, (list, tuple)) or len(level) != 2:
                raise SpotDataError("invalid_market_data")
            rows.append([_number(level[0], positive=True), _number(level[1], nonnegative=True)])
        prices = [r[0] for r in rows]
        if side == "bids" and prices != sorted(prices, reverse=True):
            raise SpotDataError("invalid_market_data")
        if side == "asks" and prices != sorted(prices):
            raise SpotDataError("invalid_market_data")
        parsed[side] = rows
    if parsed["bids"][0][0] >= parsed["asks"][0][0]:
        raise SpotDataError("invalid_market_data")
    stamp = _timestamp(raw.get("timestamp"))
    result.update({
        "timestamp": stamp,
        "quality": _freshness(stamp, max_age_seconds=60),
        "bids": parsed["bids"], "asks": parsed["asks"],
        "bid_quote_depth": sum(p * qty for p, qty in parsed["bids"]),
        "ask_quote_depth": sum(p * qty for p, qty in parsed["asks"]),
    })
    if not math.isfinite(result["bid_quote_depth"]) or not math.isfinite(result["ask_quote_depth"]):
        raise SpotDataError("invalid_market_data")
    total = result["bid_quote_depth"] + result["ask_quote_depth"]
    result["depth_imbalance"] = (
        (result["bid_quote_depth"] - result["ask_quote_depth"]) / total if total > 0 else None
    )
    return result


def _params(dataset: Dataset, symbol: str, timeframe: str, limit: int) -> tuple[str, dict]:
    if not SYMBOL_PATTERN.fullmatch(symbol):
        raise SpotDataError("invalid_symbol")
    if timeframe not in TIMEFRAMES or dataset == "ohlcv" and not 20 <= limit <= 300:
        raise SpotDataError("invalid_parameters")
    if dataset == "orderbook" and limit not in {5, 10, 20, 50, 100}:
        raise SpotDataError("invalid_parameters")
    if dataset not in CACHE_TTLS:
        raise SpotDataError("invalid_parameters")
    path = {"ticker": "/ticker", "ohlcv": "/ohlcv", "orderbook": "/orderbook"}[dataset]
    values: dict[str, Any] = {"symbol": symbol}
    if dataset == "ohlcv":
        values.update({"timeframe": timeframe, "limit": limit})
    elif dataset == "orderbook":
        values["limit"] = limit
    return "/api/v1/markets/spot" + path, values


async def _request(path: str, params: dict, key: str, base: str) -> Any:
    # The Trading Office ExchangeService handles retries/circuit breaking.
    # We never follow redirects or use environment HTTP proxies.
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(13.0, connect=3.0),
                                    follow_redirects=False, trust_env=False) as client:
            async with client.stream("GET", base + path, params=params, headers={
                "X-API-Key": key, "Accept": "application/json",
            }) as response:
                if response.status_code == 400:
                    raise SpotDataError("unsupported_symbol")
                if response.status_code == 429:
                    raise SpotDataError("rate_limited")
                if response.status_code != 200:
                    raise SpotDataError("upstream_unavailable")
                if "application/json" not in response.headers.get("content-type", "").lower():
                    raise SpotDataError("invalid_market_data")
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_BODY_SIZE:
                        raise SpotDataError("oversized_market_data")
                try:
                    return json.loads(body)
                except (TypeError, ValueError) as exc:
                    raise SpotDataError("invalid_market_data") from exc
    except SpotDataError:
        raise
    except (httpx.HTTPError, OSError, ValueError) as exc:
        raise SpotDataError("upstream_unavailable") from exc


async def spot_data(dataset: Dataset, symbol: str, timeframe: str = "1h", limit: int = 100) -> dict:
    path, params = _params(dataset, symbol, timeframe, limit)
    try:
        base, key = _connection_settings()
    except Exception as exc:
        raise SpotDataError("not_configured") from exc
    cache_key = (dataset, symbol, timeframe if dataset == "ohlcv" else "", limit if dataset != "ticker" else 0)
    with _LOCK:
        cached = _CACHE.get(cache_key)
        if cached and cached[0] > time.monotonic():
            return {**cached[1], "cached": True}
    upstream = await _request(path, params, key, base)
    if dataset == "ticker":
        value = validate_ticker(upstream, symbol)
    elif dataset == "ohlcv":
        value = validate_ohlcv(upstream, symbol, timeframe, limit)
    else:
        value = validate_orderbook(upstream, symbol, limit)
    with _LOCK:
        if len(_CACHE) > 128:
            _CACHE.clear()
        _CACHE[cache_key] = (time.monotonic() + CACHE_TTLS[dataset], value)
    return {**value, "cached": False}
