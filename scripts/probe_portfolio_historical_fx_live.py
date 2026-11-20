# -*- coding: utf-8 -*-
"""Read-only live Yahoo historical-FX evidence check. No orders, DB or secrets.

Run on a networked machine with yfinance:
    python scripts/probe_portfolio_historical_fx_live.py

The requested date is NOT the source-bar date. A closed market, a weekend or
the provider may return an older (correctly dated) close. Fresh/stale decisions
use the portfolio's max three CALENDAR days; this observation never stores FX.
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yfinance as yf

from src.services.portfolio_historical_fx import (
    MAX_HISTORICAL_FX_RATE_AGE_DAYS,
    fetch_dated_yahoo_fx_close,
)

# Observed reference dates, not claims that individual exchange markets closed.
DATES = (
    ("most-recent-day", datetime.now(timezone.utc).date()),
    ("known-Sunday", date(2026, 11, 15)),
    ("New-Year-day", date(2026, 1, 1)),
)
CURRENCY_PAIRS = (("USD", "TRY"), ("USD", "CNY"), ("USD", "JPY"), ("USD", "HKD"))


def main() -> int:
    valid_observations = 0
    unavailable = 0
    stale = 0
    future = 0
    unclosed = 0
    print("POLICY current UTC daily candle is unverified and excluded; last completed source bar only", flush=True)
    for label, target_date in DATES:
        print(f"CASE {label} request_date={target_date.isoformat()}", flush=True)
        for origin, target in CURRENCY_PAIRS:
            pair = f"{origin}/{target}"
            try:
                quote = fetch_dated_yahoo_fx_close(
                    from_currency=origin,
                    to_currency=target,
                    as_of_date=target_date,
                    provider=yf,
                )
            except Exception as exc:
                print(f"  {pair} UNAVAILABLE provider_error={type(exc).__name__}: {exc}", flush=True)
                unavailable += 1
                continue

            if quote is None:
                print(f"  {pair} UNAVAILABLE (missing/invalid/future-dated source)", flush=True)
                unavailable += 1
                continue
            value, source_date = quote
            age = (target_date - source_date).days
            if age < 0:
                future += 1
                print(f"  {pair} UNSAFE_FUTURE source_date={source_date}", flush=True)
                continue
            if label == "most-recent-day" and source_date >= target_date:
                unclosed += 1
                print(f"  {pair} UNSAFE_UNFINALIZED_DAILY_BAR source_date={source_date}", flush=True)
                continue
            state = "CURRENT_FOR_HISTORICAL_VALUATION" if age <= MAX_HISTORICAL_FX_RATE_AGE_DAYS else "STALE_FOR_RISK"
            print(
                f"  {pair} source_date={source_date.isoformat()} "
                f"request_date={target_date.isoformat()} age_days={age} "
                f"rate={value:.8f} status={state}",
                flush=True,
            )
            valid_observations += 1
            if age > MAX_HISTORICAL_FX_RATE_AGE_DAYS:
                stale += 1

    total = len(DATES) * len(CURRENCY_PAIRS)
    print(
        f"SUMMARY examined={total} date_verified={valid_observations} "
        f"expected_stale={stale} unavailable={unavailable} "
        f"unsafe_future={future} unsafe_unclosed={unclosed}",
        flush=True,
    )
    # Outages and provider gaps mean NOT VERIFIED, never a risk authorization.
    # Stale but properly dated source bars ARE evidence of safe age handling.
    return 0 if valid_observations == total and future == 0 and unclosed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
