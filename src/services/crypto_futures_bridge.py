"""EBBot read-only Binance USD-M futures market data.

Market ticker/candles/depth/funding come from the isolated Trading Office
public-data routes. Open interest uses Binance's documented public USD-M API.
No signed Binance API, exchange balances, trade routes or paper mutations.
"""
from __future__ import annotations

import asyncio
import json
import math
import re
import threading
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

import httpx

from src.services.crypto_office_bridge import _connection_settings
from src.services.crypto_spot_bridge import (
    SpotDataError,
    TIMEFRAMES,
    validate_ohlcv,
    validate_orderbook,
    validate_ticker,
)

FuturesDataset = Literal["ticker", "ohlcv", "orderbook", "funding", "open-interest"]
FUTURES_PAIR = re.compile(r"^[A-Z0-9]{2,20}/USDT$")
DATASET_TTLS = {
    "ticker": 6.0,
    "ohlcv": 30.0,
    "orderbook": 5.0,
    "funding": 12.0,
    "open-interest": 15.0,
}
MAX_RESPONSE_BYTES = 350_000
OPEN_INTEREST_API = "https://fapi.binance.com/fapi/v1/openInterest"
_CACHE: dict[tuple, tuple[float, dict]] = {}
_FAILURES: dict[str, tuple[int, float]] = {}
_LOCK = threading.RLock()


class FuturesDataError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def normalize_pair(value: str) -> tuple[str, str, str]:
    if not isinstance(value, str):
        raise FuturesDataError("invalid_symbol")
    pair = value.strip().upper()
    if not FUTURES_PAIR.fullmatch(pair):
        raise FuturesDataError("invalid_symbol")
    base = pair.split("/", 1)[0]
    # CCXT's USD-M linear perpetual instrument identity has :USDT settlement.
    return pair, pair + ":USDT", base + "USDT"


def _finite(raw: Any, *, positive: bool = False, nonnegative: bool = False) -> float:
    if isinstance(raw, bool) or not isinstance(raw, (int, float)) or not math.isfinite(raw):
        raise FuturesDataError("invalid_market_data")
    num = float(raw)
    if positive and num <= 0 or nonnegative and num < 0:
        raise FuturesDataError("invalid_market_data")
    return num


def _optional_positive(raw: Any) -> float | None:
    return None if raw is None else _finite(raw, positive=True)


def _timestamp(raw: Any, *, required: bool = False, max_age: float | None = None) -> int | None:
    if raw is None and not required:
        return None
    if isinstance(raw, bool) or not isinstance(raw, int) or raw <= 0:
        raise FuturesDataError("invalid_market_data")
    now_ms = time.time() * 1000
    if raw > now_ms + 5 * 60_000:
        raise FuturesDataError("future_market_data")
    if max_age is not None and raw < now_ms - max_age * 1000:
        raise FuturesDataError("stale_market_data")
    return raw


def validate_funding(raw: Any, contract: str, pair: str) -> dict:
    if (not isinstance(raw, dict) or raw.get("market") != "futures"
            or raw.get("symbol") != contract
            or raw.get("source") != "Binance USD-M Futures public market data"):
        raise FuturesDataError("wrong_market_identity")
    rate = _finite(raw.get("funding_rate"))
    if abs(rate) > 0.1:  # anomalous/malformed observations must not become estimates
        raise FuturesDataError("invalid_market_data")
    mark = _finite(raw.get("mark_price"), positive=True)
    index = _optional_positive(raw.get("index_price"))
    hours = raw.get("funding_interval_hours")
    interval = raw.get("funding_interval_ms")
    if (isinstance(hours, bool) or hours not in (1, 2, 4, 8)
            or isinstance(interval, bool) or interval != hours * 3_600_000):
        raise FuturesDataError("invalid_market_data")
    # CCXT fundingTimestamp can denote the prior or next settlement and must
    # not be mistaken for a feed observation time.
    schedule_timestamp = raw.get("funding_timestamp")
    next_funding = raw.get("next_funding_timestamp")
    for stamp in (schedule_timestamp, next_funding):
        if stamp is not None and (isinstance(stamp, bool) or not isinstance(stamp, int) or stamp <= 0):
            raise FuturesDataError("invalid_market_data")
    if next_funding is not None:
        now = time.time() * 1000
        if next_funding < now - 24 * 3_600_000 or next_funding > now + 48 * 3_600_000:
            raise FuturesDataError("invalid_market_data")
    return {
        "market": "futures", "symbol": pair, "contract": contract,
        "provider": "Binance", "source": raw["source"], "orders_enabled": False,
        "funding_rate": rate, "funding_interval_hours": hours,
        "funding_interval_ms": interval,
        "funding_timestamp": schedule_timestamp,
        "next_funding_timestamp": next_funding,
        "mark_price": mark, "index_price": index,
        # Fundings' schedule time is not a proven current quote timestamp.
        "quality": "unknown",
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def validate_open_interest(raw: Any, pair: str, binance_symbol: str) -> dict:
    if (not isinstance(raw, dict) or raw.get("symbol") != binance_symbol
            or isinstance(raw.get("openInterest"), bool)):
        raise FuturesDataError("wrong_market_identity")
    # Binance returns the quantity as a decimal string in base-asset units.
    value = raw.get("openInterest")
    if not isinstance(value, str) or len(value) > 48:
        raise FuturesDataError("invalid_market_data")
    try:
        decimal_value = Decimal(value)
        if not decimal_value.is_finite() or decimal_value < 0:
            raise ValueError()
        quantity = float(decimal_value)
        if not math.isfinite(quantity):
            raise ValueError()
    except (InvalidOperation, TypeError, ValueError, OverflowError) as exc:
        raise FuturesDataError("invalid_market_data") from exc
    stamp = _timestamp(raw.get("time"), required=True, max_age=180)
    return {
        "market": "futures", "symbol": pair, "binance_symbol": binance_symbol,
        "open_interest": quantity, "unit": pair.split("/")[0],
        "timestamp": stamp, "quality": "ok",
        "provider": "Binance", "source": "Binance USD-M Futures public openInterest",
        "checked_at": datetime.now(timezone.utc).isoformat(), "orders_enabled": False,
    }


def _validate_common(raw: Any, dataset: FuturesDataset, pair: str, contract: str, timeframe: str, limit: int) -> dict:
    try:
        if dataset == "ticker":
            result = validate_ticker(raw, contract, market="futures")
        elif dataset == "ohlcv":
            result = validate_ohlcv(raw, contract, timeframe, limit, market="futures")
        elif dataset == "orderbook":
            result = validate_orderbook(raw, contract, limit, market="futures")
        elif dataset == "funding":
            return validate_funding(raw, contract, pair)
        else:
            raise FuturesDataError("invalid_parameters")
    except SpotDataError as exc:
        raise FuturesDataError(exc.code) from exc
    result["contract"] = contract
    result["symbol"] = pair
    return result


async def _bounded_get(url: str, *, params: dict, headers: dict | None = None) -> dict:
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(13.0, connect=3.0),
            follow_redirects=False, trust_env=False,
        ) as client:
            async with client.stream("GET", url, params=params, headers={
                "Accept": "application/json", **(headers or {}),
            }) as response:
                if response.status_code in (400, 404):
                    raise FuturesDataError("unsupported_symbol")
                if response.status_code in (418, 429):
                    raise FuturesDataError("rate_limited")
                if response.status_code != 200:
                    raise FuturesDataError("upstream_unavailable")
                if "application/json" not in response.headers.get("content-type", "").lower():
                    raise FuturesDataError("invalid_market_data")
                raw = bytearray()
                async for piece in response.aiter_bytes():
                    raw.extend(piece)
                    if len(raw) > MAX_RESPONSE_BYTES:
                        raise FuturesDataError("oversized_market_data")
                try:
                    body = json.loads(raw)
                except (TypeError, ValueError) as exc:
                    raise FuturesDataError("invalid_market_data") from exc
                if not isinstance(body, dict):
                    raise FuturesDataError("invalid_market_data")
                return body
    except FuturesDataError:
        raise
    except (httpx.HTTPError, ValueError, OSError) as exc:
        raise FuturesDataError("upstream_unavailable") from exc


def _route(dataset: FuturesDataset, contract: str, timeframe: str, limit: int) -> tuple[str, dict]:
    path = {
        "ticker": "/api/v1/markets/futures/ticker",
        "ohlcv": "/api/v1/markets/futures/ohlcv",
        "orderbook": "/api/v1/markets/futures/orderbook",
        "funding": "/api/v1/markets/futures/funding-rate",
    }[dataset]
    query: dict[str, Any] = {"symbol": contract}
    if dataset == "ohlcv":
        if timeframe not in TIMEFRAMES or not 20 <= limit <= 300:
            raise FuturesDataError("invalid_parameters")
        query.update({"timeframe": timeframe, "limit": limit})
    if dataset == "orderbook":
        if limit not in (5, 10, 20, 50, 100):
            raise FuturesDataError("invalid_parameters")
        query["limit"] = limit
    return path, query


def _still_fresh(value: dict) -> bool:
    quality = value.get("quality")
    if quality == "unknown":  # never upgrade no-timestamp observations
        return True
    stamp = value.get("timestamp")
    if stamp is None:
        stamp = value.get("last_candle_timestamp")
    if isinstance(stamp, bool) or not isinstance(stamp, int):
        return False
    age = time.time() * 1000 - stamp
    window = 60
    if "candles" in value:
        window = TIMEFRAMES.get(value.get("timeframe"), 0) * 3 + 180
    elif "open_interest" in value or "last" in value:
        window = 180
    return -300_000 <= age <= window * 1000


async def futures_data(dataset: FuturesDataset, symbol: str, timeframe: str = "1h", limit: int = 100) -> dict:
    pair, contract, binance_symbol = normalize_pair(symbol)
    if dataset not in DATASET_TTLS:
        raise FuturesDataError("invalid_parameters")
    if dataset != "open-interest":
        path, params = _route(dataset, contract, timeframe, limit)
    else:
        path, params = OPEN_INTEREST_API, {"symbol": binance_symbol}

    # All Futures reads follow the global live-trading hard stop.
    if __import__("os").getenv("TRADING_ENABLED", "false").lower() not in ("", "0", "false", "no"):
        raise FuturesDataError("unsafe_mode")
    key = (dataset, pair, timeframe if dataset == "ohlcv" else "", limit if dataset == "orderbook" else 0)
    with _LOCK:
        cached = _CACHE.get(key)
        if cached and time.monotonic() < cached[0] and _still_fresh(cached[1]):
            return {**cached[1], "cached": True}
        if _FAILURES.get(dataset, (0, 0.0))[1] > time.monotonic():
            raise FuturesDataError("circuit_open")
    try:
        if dataset == "open-interest":
            source = await _bounded_get(OPEN_INTEREST_API, params=params)
            value = validate_open_interest(source, pair, binance_symbol)
        else:
            try:
                base, secret = _connection_settings()
            except Exception as exc:
                raise FuturesDataError("not_configured") from exc
            raw = await _bounded_get(base + path, params=params, headers={"X-API-Key": secret})
            value = _validate_common(raw, dataset, pair, contract, timeframe, limit)
    except FuturesDataError as exc:
        # Backoff only for network/availability errors, not bad user parameters.
        if exc.code in ("upstream_unavailable", "rate_limited"):
            with _LOCK:
                failures = _FAILURES.get(dataset, (0, 0))[0] + 1
                _FAILURES[dataset] = (failures, time.monotonic() + min(30, 2 ** min(failures, 5)))
        raise
    with _LOCK:
        _FAILURES.pop(dataset, None)
        if len(_CACHE) >= 128:
            _CACHE.clear()
        _CACHE[key] = (time.monotonic() + DATASET_TTLS[dataset], value)
    return {**value, "cached": False}
