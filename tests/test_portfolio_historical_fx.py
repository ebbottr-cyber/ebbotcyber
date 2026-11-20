# -*- coding: utf-8 -*-
"""Isolated source-date evidence tests for Yahoo daily FX on market-closed dates."""

from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import MagicMock

import pandas as pd

from src.services.portfolio_historical_fx import (
    MAX_HISTORICAL_FX_RATE_AGE_DAYS,
    fetch_dated_yahoo_fx_close,
)


class DatedHistoricalFxTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = MagicMock()

    def _set_bars(self, timestamps, closes, *, timezone="UTC") -> None:
        self.provider.Ticker.return_value.history.return_value = pd.DataFrame(
            {"Close": closes},
            index=pd.DatetimeIndex(timestamps, tz=timezone),
        )

    def fetch(self, target: date = date(2026, 1, 4), *, current_utc_date=None):
        return fetch_dated_yahoo_fx_close(
            from_currency="USD", to_currency="CNY",
            as_of_date=target, provider=self.provider,
            current_utc_date=current_utc_date,
        )

    def test_weekend_uses_friday_source_date_instead_of_sunday(self) -> None:
        self._set_bars(["2026-01-02 17:00"], [7.1], timezone="America/New_York")
        self.assertEqual(self.fetch(date(2026, 1, 4)), (7.1, date(2026, 1, 2)))
        kwargs = self.provider.Ticker.return_value.history.call_args.kwargs
        self.assertEqual(self.provider.Ticker.call_args.args[0], "USDCNY=X")
        self.assertEqual(kwargs["interval"], "1d")
        self.assertEqual(kwargs["end"], "2026-01-05")

    def test_new_year_holiday_retains_prior_year_bar_date(self) -> None:
        self._set_bars(["2025-12-31"], [7.17])
        value, source_date = self.fetch(date(2026, 1, 1))
        self.assertEqual(value, 7.17)
        self.assertEqual(source_date, date(2025, 12, 31))
        self.assertLessEqual((date(2026, 1, 1) - source_date).days, MAX_HISTORICAL_FX_RATE_AGE_DAYS)

    def test_older_than_long_weekend_is_not_falsely_fresh(self) -> None:
        self._set_bars(["2026-01-02"], [7.1])
        result = self.fetch(date(2026, 1, 6))
        self.assertEqual(result, (7.1, date(2026, 1, 2)))
        self.assertGreater((date(2026, 1, 6) - result[1]).days, MAX_HISTORICAL_FX_RATE_AGE_DAYS)

    def test_source_date_comes_from_latest_chronological_valid_close(self) -> None:
        self._set_bars(["2026-01-02", "2025-12-31", "2026-01-03"], [7.1, 7.0, float("nan")])
        self.assertEqual(self.fetch(), (7.1, date(2026, 1, 2)))

    def test_future_dated_bar_is_rejected_even_when_price_is_valid(self) -> None:
        self._set_bars(["2026-01-05"], [7.1])
        self.assertIsNone(self.fetch(date(2026, 1, 4)))

    def test_nonfinite_zero_or_missing_close_does_not_create_fx_quote(self) -> None:
        for price in (float("nan"), float("inf"), 0.0, -2.0):
            with self.subTest(price=price):
                self._set_bars(["2026-01-02"], [price])
                self.assertIsNone(self.fetch())

    def test_today_daily_bar_excluded_even_with_valid_close(self) -> None:
        today = date(2026, 11, 20)
        self._set_bars(["2026-11-19", "2026-11-20"], [7.0, 7.5])
        # The newest bar may still be changing even if its price is finite.
        self.assertEqual(self.fetch(today, current_utc_date=today), (7.0, date(2026, 11, 19)))

    def test_today_only_daily_candle_never_masquerades_as_final_close(self) -> None:
        today = date(2026, 11, 20)
        self._set_bars(["2026-11-20"], [7.5])
        self.assertIsNone(self.fetch(today, current_utc_date=today))

    def test_past_asof_date_accepts_same_date_historical_close(self) -> None:
        today = date(2026, 11, 20)
        self._set_bars(["2026-11-18", "2026-11-19"], [7.0, 7.3])
        self.assertEqual(
            self.fetch(date(2026, 11, 19), current_utc_date=today),
            (7.3, date(2026, 11, 19)),
        )

    def test_today_market_timezone_date_is_not_converted_to_utc_date(self) -> None:
        today = date(2026, 11, 20)
        self._set_bars(
            ["2026-11-19 16:00", "2026-11-20 21:00"],
            [7.0, 7.5], timezone="America/New_York",
        )
        self.assertEqual(self.fetch(today, current_utc_date=today), (7.0, date(2026, 11, 19)))

    def test_weekend_uses_friday_and_rejects_any_sunday_provisional_bar(self) -> None:
        sunday = date(2026, 11, 22)
        self._set_bars(["2026-11-20", "2026-11-22"], [7.1, 8.0])
        self.assertEqual(self.fetch(sunday, current_utc_date=sunday), (7.1, date(2026, 11, 20)))

    def test_future_bar_does_not_silently_fallback_to_older_bar(self) -> None:
        today = date(2026, 11, 20)
        self._set_bars(["2026-11-19", "2026-11-21"], [7.0, 7.5])
        self.assertIsNone(self.fetch(today, current_utc_date=today))

    def test_current_day_with_nonfinite_price_keeps_prior_valid_close(self) -> None:
        today = date(2026, 11, 20)
        self._set_bars(["2026-11-19", "2026-11-20"], [7.0, float("nan")])
        self.assertEqual(self.fetch(today, current_utc_date=today), (7.0, date(2026, 11, 19)))

    def test_missing_provider_or_unverifiable_index_fails_closed(self) -> None:
        self.assertIsNone(fetch_dated_yahoo_fx_close(
            from_currency="USD", to_currency="TRY",
            as_of_date=date(2026, 1, 4), provider=None,
        ))
        self.provider.Ticker.return_value.history.return_value = pd.DataFrame(
            {"Close": [7.1]}, index=["not-a-date"],
        )
        self.assertIsNone(self.fetch())


if __name__ == "__main__":
    unittest.main()
