# -*- coding: utf-8 -*-
"""Indicative TRY display rates. No trading, ledger mutation or 1:1 FX fallback.

CNY/TRY is computed from contemporaneous USD/TRY and USD/CNY quotes.
This endpoint is intentionally separate from portfolio transaction currency.
"""

from __future__ import annotations

import logging
import math
import threading
import time
from datetime import datetime, timezone
from typing import Any, Optional, Tuple

logger = logging.getLogger(__name__)

# Quotes more than 30 minutes old are not advertised as current.
MAX_QUOTE_AGE_SECONDS = 1800
MAX_PAIR_TIMESTAMP_GAP_SECONDS = 900
CACHE_SECONDS = 60

_cache_lock = threading.Lock()
_cache_until = 0.0
_cache_value: Optional[dict[str, Any]] = None


def build_try_display_rates(
    usd_try: Optional[Tuple[float, datetime]],
    usd_cny: Optional[Tuple[float, datetime]],
    *,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """Validate BOTH quote ages and compute 1 CNY = (USD/TRY)/(USD/CNY) TRY."""
    instant = now or datetime.now(timezone.utc)
    result: dict[str, Any] = {
        "status": "unavailable",
        "usd_try": None,
        "usd_cny": None,
        "cny_try": None,
        "as_of": None,
        "source": "Yahoo Finance FX intraday (indicative)",
    }
    if not usd_try or not usd_cny:
        return result

    try:
        dollar_try, try_time = usd_try
        dollar_cny, cny_time = usd_cny
        if (not math.isfinite(dollar_try) or not math.isfinite(dollar_cny)
                or dollar_try <= 0 or dollar_cny <= 0):
            return result
        if (try_time.tzinfo is None or cny_time.tzinfo is None
                or instant.tzinfo is None):
            return result
        try_age = (instant - try_time).total_seconds()
        cny_age = (instant - cny_time).total_seconds()
        gap = abs((try_time - cny_time).total_seconds())
        if not (0 <= try_age <= MAX_QUOTE_AGE_SECONDS
                and 0 <= cny_age <= MAX_QUOTE_AGE_SECONDS
                and gap <= MAX_PAIR_TIMESTAMP_GAP_SECONDS):
            return {**result, "status": "stale"}
        converted = dollar_try / dollar_cny
        if not math.isfinite(converted) or converted <= 0:
            return result
        return {
            **result,
            "status": "current",
            "usd_try": round(float(dollar_try), 8),
            "usd_cny": round(float(dollar_cny), 8),
            "cny_try": round(float(converted), 8),
            "as_of": min(try_time, cny_time).astimezone(timezone.utc).isoformat(),
        }
    except (TypeError, ValueError, OverflowError):
        return result


def _intraday_quote(symbol: str) -> Optional[Tuple[float, datetime]]:
    try:
        import yfinance as yf

        # Yahoo data can be delayed or unavailable, especially outside FX sessions.
        history = yf.Ticker(symbol).history(
            period="5d",
            interval="5m",
            auto_adjust=False,
            timeout=8,
        )
        if history is None or history.empty or "Close" not in history:
            return None
        prices = history["Close"].dropna()
        if prices.empty:
            return None
        value = float(prices.iloc[-1])
        timestamp = prices.index[-1]
        if hasattr(timestamp, "to_pydatetime"):
            timestamp = timestamp.to_pydatetime()
        if not isinstance(timestamp, datetime) or timestamp.tzinfo is None:
            return None
        return value, timestamp.astimezone(timezone.utc)
    except Exception as exc:
        logger.warning("Indicative FX quote unavailable for %s: %s", symbol, exc)
        return None


def get_try_display_rates() -> dict[str, Any]:
    """Return small cached, read-only display rates; never invent missing quotes."""
    global _cache_until, _cache_value
    with _cache_lock:
        if _cache_value is not None and time.monotonic() < _cache_until:
            return dict(_cache_value)
        result = build_try_display_rates(
            _intraday_quote("USDTRY=X"),
            _intraday_quote("USDCNY=X"),
        )
        _cache_value = result
        _cache_until = time.monotonic() + CACHE_SECONDS
        return dict(result)
