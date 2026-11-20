# -*- coding: utf-8 -*-
"""Date-verifiable Yahoo daily FX closes, separate from intraday display FX.

Do not turn historical daily closes into a current quote: the original bar date
must accompany the price and age checks belong to the valuation caller.
This module has no portfolio DB, order or scheduled execution dependencies.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from typing import Any, Optional, Tuple

MAX_HISTORICAL_FX_RATE_AGE_DAYS = 3
DatedFxQuote = Tuple[float, date]


def fetch_dated_yahoo_fx_close(
    *,
    from_currency: str,
    to_currency: str,
    as_of_date: date,
    provider: Any,
) -> Optional[DatedFxQuote]:
    """Return (close, *source-bar date*), or None if provenance is unusable.

    The provider is injected to keep this same code path testable without a
    network and independently observable on an isolated GitHub runner.
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
    value = float(closes.iloc[-1])
    timestamp = closes.index[-1]
    if hasattr(timestamp, "to_pydatetime"):
        timestamp = timestamp.to_pydatetime()
    if isinstance(timestamp, datetime):
        # Respect Yahoo's exchange-local daily-bar calendar date.
        source_date = timestamp.date()
    elif type(timestamp) is date:
        source_date = timestamp
    else:
        return None
    if not math.isfinite(value) or value <= 0 or source_date > as_of_date:
        return None
    return value, source_date
