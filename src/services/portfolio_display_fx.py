# -*- coding: utf-8 -*-
"""Read-only indicative TRY display rates, isolated from ledger and risk FX.

Each currency pair is independently validated against USD/TRY, including both
quote age and timestamp skew. Missing/stale quotes remain unavailable; no
last-known, synthetic 1:1 or previous-session rate is presented as current.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import logging
import math
import threading
import time
from datetime import datetime, timezone
from typing import Any, Mapping, Optional, Tuple

logger = logging.getLogger(__name__)

MAX_QUOTE_AGE_SECONDS = 1800
MAX_PAIR_TIMESTAMP_GAP_SECONDS = 900
CACHE_SECONDS = 60
CROSS_CURRENCIES = ("CNY", "HKD", "JPY", "KRW", "TWD")
YAHOO_SYMBOLS = {
    "USD": "USDTRY=X",
    "CNY": "USDCNY=X",
    "HKD": "USDHKD=X",
    "JPY": "USDJPY=X",
    "KRW": "USDKRW=X",
    "TWD": "USDTWD=X",
}

Quote = Tuple[float, datetime]
_cache_lock = threading.Lock()
_cache_until = 0.0
_cache_value: Optional[dict[str, Any]] = None


def _quote_state(quote: Optional[Quote], now: datetime) -> str:
    """Reject invalid quotes, naive clocks, future timestamps and old prices."""
    if quote is None:
        return "unavailable"
    try:
        price, timestamp = quote
        if (not isinstance(timestamp, datetime) or timestamp.tzinfo is None
                or now.tzinfo is None or not math.isfinite(float(price))
                or float(price) <= 0):
            return "unavailable"
        age = (now - timestamp).total_seconds()
        return "current" if 0 <= age <= MAX_QUOTE_AGE_SECONDS else "stale"
    except (TypeError, ValueError, OverflowError):
        return "unavailable"


def build_try_display_rates(
    usd_try: Optional[Quote],
    usd_cny: Optional[Quote],
    *,
    additional_quotes: Optional[Mapping[str, Optional[Quote]]] = None,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """Calculate 1 foreign currency in TRY, never from an unverified cross."""
    instant = now or datetime.now(timezone.utc)
    others = additional_quotes or {}
    quotes: dict[str, Optional[Quote]] = {"CNY": usd_cny}
    quotes.update({c: others.get(c) for c in CROSS_CURRENCIES if c != "CNY"})
    result: dict[str, Any] = {
        "status": "unavailable",
        "usd_try": None,
        "usd_cny": None,
        "cny_try": None,
        "hkd_try": None,
        "jpy_try": None,
        "krw_try": None,
        "twd_try": None,
        "as_of": None,
        "pair_status": {},
        "pair_as_of": {},
        "source": "Yahoo Finance FX intraday (indicative, delayed possible)",
    }
    usd_state = _quote_state(usd_try, instant)
    result["pair_status"]["USD"] = usd_state
    if usd_state == "current":
        usd_value, usd_time = usd_try
        result["usd_try"] = round(float(usd_value), 8)
        result["pair_as_of"]["USD"] = usd_time.astimezone(timezone.utc).isoformat()

    for currency in CROSS_CURRENCIES:
        foreign_quote = quotes[currency]
        foreign_state = _quote_state(foreign_quote, instant)
        if usd_state != "current":
            pair_state = usd_state
        elif foreign_state != "current":
            pair_state = foreign_state
        else:
            usd_value, usd_time = usd_try
            foreign_value, foreign_time = foreign_quote
            time_gap = abs((usd_time - foreign_time).total_seconds())
            pair_state = "stale" if time_gap > MAX_PAIR_TIMESTAMP_GAP_SECONDS else "current"
            if pair_state == "current":
                converted = float(usd_value) / float(foreign_value)
                if not math.isfinite(converted) or converted <= 0:
                    pair_state = "unavailable"
                else:
                    result[f"{currency.lower()}_try"] = round(converted, 8)
                    result["pair_as_of"][currency] = (
                        min(usd_time, foreign_time).astimezone(timezone.utc).isoformat()
                    )
                    if currency == "CNY":
                        result["usd_cny"] = round(float(foreign_value), 8)
        result["pair_status"][currency] = pair_state

    # Legacy status/as_of describe CNY cross for existing clients; new clients
    # must rely on per-currency status and timestamp for independent validity.
    result["status"] = result["pair_status"]["CNY"]
    result["as_of"] = result["pair_as_of"].get("CNY")
    return result


def _intraday_quote(symbol: str) -> Optional[Quote]:
    try:
        import yfinance as yf

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
    """Cache read-only display quotes; never write to risk/transaction tables."""
    global _cache_until, _cache_value
    with _cache_lock:
        if _cache_value is not None and time.monotonic() < _cache_until:
            return dict(_cache_value)
        with ThreadPoolExecutor(max_workers=4) as workers:
            futures = {code: workers.submit(_intraday_quote, symbol)
                       for code, symbol in YAHOO_SYMBOLS.items()}
            quotes = {code: future.result() for code, future in futures.items()}
        result = build_try_display_rates(
            quotes["USD"],
            quotes["CNY"],
            additional_quotes={code: quotes[code] for code in CROSS_CURRENCIES if code != "CNY"},
        )
        _cache_value = result
        _cache_until = time.monotonic() + CACHE_SECONDS
        return dict(result)
