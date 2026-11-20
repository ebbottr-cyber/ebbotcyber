# -*- coding: utf-8 -*-
"""Date-verifiable Yahoo daily FX closes, separate from intraday display FX.

Do not turn historical daily closes into a current quote: the original bar date
must accompany the price and age checks belong to the valuation caller.
This module has no portfolio DB, order or scheduled execution dependencies.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional, Tuple

MAX_HISTORICAL_FX_RATE_AGE_DAYS = 3
DatedFxQuote = Tuple[float, date]


def fetch_dated_yahoo_fx_close(
    *,
    from_currency: str,
    to_currency: str,
    as_of_date: date,
    provider: Any,
    current_utc_date: Optional[date] = None,
) -> Optional[DatedFxQuote]:
    """Return (close, *source-bar date*), or None if provenance is unusable.

    The provider is injected to keep this same code path testable without a
    network and independently observable on an isolated GitHub runner.
    Without a trusted close-finalization marker, today's 1d candle is not
    considered a completed close, even after local market hours. A prior
    bar is returned with its original source date or None if none exists.
    """
    if provider is None:
        return None
    ticker = provider.Ticker(f"{from_currency}{to_currency}=X")
    history = ticker.history(
        start=(as_of_date - timedelta(days=7)).isoformat(),
        end=(as_of_date + timedelta(days=1)).isoformat(),
        interval="1d",
        auto_adjust=False,
        timeout=8,
    )
    if history is None or history.empty or "Close" not in history:
        return None
    closes = history["Close"].dropna().sort_index()
    if closes.empty:
        return None

    # Yahoo's most recent 1d candle may be a *still-changing intraday bar*.
    # There is no provider-supplied "final" bit here. Fail closed for every
    # current UTC calendar-day bar (including markets already closed locally).
    # This intentionally trades some freshness for a verifiable historical
    # close. A historical as_of_date before today can still use that day's bar.
    utc_today = current_utc_date if current_utc_date is not None else datetime.now(timezone.utc).date()
    if type(utc_today) is not date:
        return None

    for timestamp, raw_value in reversed(list(closes.items())):
        if hasattr(timestamp, "to_pydatetime"):
            timestamp = timestamp.to_pydatetime()
        if isinstance(timestamp, datetime):
            # Preserve the provider's exchange-local bar date, NOT UTC date.
            source_date = timestamp.date()
        elif type(timestamp) is date:
            source_date = timestamp
        else:
            return None

        if source_date > as_of_date:
            # An unexpected future candle is not trustworthy. Do not fall
            # back through an inconsistent time series.
            return None
        if source_date >= utc_today:
            # Unfinalized/undocumented same-day close: skip to a prior bar,
            # NEVER stamp today's request date onto that prior close.
            continue

        value = float(raw_value)
        if not math.isfinite(value) or value <= 0:
            return None
        return value, source_date

    return None
