"""Prevent pandas compatibility warnings from screening and ETF date selection."""

import warnings

import pandas as pd
import pytest

from src.core.etf_rotation import rebalance_dates
from src.services.screening import daily


def test_daily_enrichment_adds_missing_columns_without_deprecated_at_assignment(monkeypatch):
    # No market/data-network calls: deterministic read-only enriched candidates.
    monkeypatch.setattr(daily, "daily_history_is_stale", lambda hist, code: False)
    monkeypatch.setattr(
        daily, "compute_daily_features",
        lambda hist: {"daily_quality_score": 95.0, "daily_quality_flags": "", "ma5": 12.5},
    )
    source = pd.DataFrame(
        {"code": ["AAPL", "MSFT"], "rank": [1, 2]}, index=["first", "second"]
    )
    original = source.copy(deep=True)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        enriched = daily.enrich_daily_features(
            source, max_rows=1, history_fetcher=lambda code, **kwargs: pd.DataFrame(),
        )

    pd.testing.assert_frame_equal(source, original)
    assert list(enriched.index) == ["first", "second"]
    assert enriched.loc["first", "daily_quality_score"] == 95.0
    assert enriched.loc["first", "ma5"] == 12.5
    assert pd.isna(enriched.loc["second", "daily_quality_score"])
    assert pd.isna(enriched.loc["second", "ma5"])
    assert enriched.attrs["daily_success_count"] == 1
    assert not any(
        "Setting a value on a DataFrame via .at" in str(warning.message)
        for warning in caught
    )


@pytest.mark.parametrize(
    ("freq", "rebalance", "expected"),
    [
        ("W", "weekly", ["2024-01-05", "2024-01-12"]),
        ("M", "monthly", ["2024-01-31", "2024-02-09"]),
    ],
)
def test_etf_rebalance_dates_keep_last_session_without_period_values_warning(
    freq, rebalance, expected,
):
    del freq  # parametrize both supported modes explicitly
    index = pd.bdate_range("2024-01-01", "2024-02-09")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = rebalance_dates(index, rebalance)

    assert list(result.strftime("%Y-%m-%d")) == expected if rebalance == "monthly" else list(result.strftime("%Y-%m-%d")) == [
        "2024-01-05", "2024-01-12", "2024-01-19", "2024-01-26", "2024-02-02", "2024-02-09",
    ]
    assert not any(
        "PeriodDtype dtype is deprecated" in str(warning.message)
        for warning in caught
    )
