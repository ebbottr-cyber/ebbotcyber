"""Read-only, fail-closed Turkish market overview backed by optional Yahoo daily bars.

No trade execution, no synthetic quotes, no user-supplied symbols. A short server-side
TTL prevents dashboard refreshes from repeatedly polling an external provider.
All values are indicative/delayed and must not be used as executable quotes.
"""
from __future__ import annotations

import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from typing import Any, Callable

SOURCE = "Yahoo Finance • günlük veri (gecikmeli)"
TTL_SECONDS = 300
MAX_AGE_DAYS = 7
OZ_TO_GRAMS = 31.1034768

# Exact provider identifiers verified against Yahoo Finance's public quote pages.
INSTRUMENTS = (
    ("bist100", "BIST 100", "XU100.IS", "TRY"),
    ("bist30", "BIST 30", "XU030.IS", "TRY"),
    ("usdtry", "USD/TRY", "TRY=X", "TRY"),
    ("eurtry", "EUR/TRY", "EURTRY=X", "TRY"),
)

_LOCK = threading.Lock()
_CACHE: dict[str, Any] | None = None
_CACHE_UNTIL = 0.0


def _unavailable(
    key: str,
    label: str,
    currency: str,
    symbol: str | None,
    *,
    status: str = "unavailable",
    as_of: str | None = None,
    note: str = "Kaynak şu anda fiyat döndürmedi.",
) -> dict[str, Any]:
    return {
        "key": key, "label": label, "symbol": symbol, "currency": currency,
        "price": None, "change_pct": None, "as_of": as_of,
        "status": status, "source": SOURCE if symbol else None,
        "note": note,
    }


def _bar_date(value: Any) -> date | None:
    try:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _positive_float(value: Any) -> float | None:
    # bool is an int subclass; a provider's true/false must not become a price.
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    if not math.isfinite(number) or number <= 0:
        return None
    return number


def _history_close_rows(frame: Any) -> list[tuple[date, float]]:
    """Parse pandas-like daily bars; accept only finite positive closes."""
    if frame is None or bool(getattr(frame, "empty", True)):
        return []
    parsed: dict[date, float] = {}
    for index, row in frame.iterrows():
        trading_date = _bar_date(index)
        close = _positive_float(row.get("Close"))
        if trading_date is not None and close is not None:
            parsed[trading_date] = close
    return sorted(parsed.items())


def quote_from_rows(
    key: str, label: str, symbol: str, currency: str,
    rows: list[tuple[date, float]], today: date,
) -> dict[str, Any]:
    """Pure quote calculation, used by both the service and offline tests."""
    valid = sorted(
        (day, value) for day, value in rows
        if isinstance(day, date) and isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value) and value > 0 and day <= today
    )
    if not valid:
        return _unavailable(key, label, currency, symbol)
    latest_day, latest_price = valid[-1]
    if (today - latest_day).days > MAX_AGE_DAYS:
        return _unavailable(
            key, label, currency, symbol, status="stale",
            as_of=latest_day.isoformat(),
            note="Son fiyat güncel değil; tutar gösterilmiyor.",
        )
    previous_prices = [value for day, value in valid[:-1] if day < latest_day]
    previous = previous_prices[-1] if previous_prices else None
    # Two individually finite daily closes can still overflow their ratio.
    # Never emit NaN/Infinity or a fabricated percentage to the JSON API.
    change = None
    if previous is not None:
        raw_change = (latest_price / previous - 1) * 100
        if math.isfinite(raw_change):
            change = round(raw_change, 4)
    return {
        "key": key, "label": label, "symbol": symbol, "currency": currency,
        "price": latest_price, "change_pct": change,
        "as_of": latest_day.isoformat(), "status": "ready",
        "source": SOURCE,
        "note": "Günlük fiyat serisi; anlık işlem kotasyonu değildir.",
    }


def _fetch_one(
    instrument: tuple[str, str, str, str],
    ticker_factory: Callable[[str], Any],
    today: date,
) -> dict[str, Any]:
    key, label, symbol, currency = instrument
    try:
        frame = ticker_factory(symbol).history(
            period="10d", interval="1d", auto_adjust=False, timeout=8
        )
        return quote_from_rows(key, label, symbol, currency, _history_close_rows(frame), today)
    except Exception:
        # Public API must never return an unverified price or the provider's diagnostics.
        return _unavailable(key, label, currency, symbol)


def build_overview(
    ticker_factory: Callable[[str], Any] | None = None,
    *,
    today: date | None = None,
) -> dict[str, Any]:
    trading_date = today or datetime.now(timezone.utc).date()
    if ticker_factory is None:
        try:
            import yfinance as yf  # Optional data provider at runtime.
            ticker_factory = yf.Ticker
        except (ImportError, RuntimeError):
            ticker_factory = None

    if ticker_factory is None:
        items = [_unavailable(*instrument[:2], instrument[3], instrument[2])
                 for instrument in INSTRUMENTS]
    else:
        with ThreadPoolExecutor(max_workers=len(INSTRUMENTS)) as executor:
            items = list(executor.map(
                lambda instrument: _fetch_one(instrument, ticker_factory, trading_date),
                INSTRUMENTS,
            ))

    # No licensed, independently verified *physical gram gold* feed in this repo.
    # Futures/spot USD per ounce must not silently masquerade as a retail TRY/gram quote.
    items.append(_unavailable(
        "gramgold", "Gram Altın", "TRY/g", None,
        note="Doğrulanmış TRY/gram altın kaynağı henüz bağlı değil.",
    ))
    return {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "cadence": "delayed_daily",
        "items": items,
    }


def get_overview() -> dict[str, Any]:
    global _CACHE, _CACHE_UNTIL
    with _LOCK:
        if _CACHE is not None and time.monotonic() < _CACHE_UNTIL:
            return _CACHE
        data = build_overview()
        _CACHE = data
        _CACHE_UNTIL = time.monotonic() + TTL_SECONDS
        return data
