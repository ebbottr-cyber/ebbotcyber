"""Deterministic offline provider-reconciliation regression tests."""
import math

import pandas as pd
import pytest

from src.core.provider_consistency import compare_adjusted_close_sources


def _series(values, days=None):
    idx = pd.bdate_range("2026-01-05", periods=len(values)) if days is None else days
    return pd.Series(values, index=idx, dtype=float)


def _compare(a, b, **kwargs):
    kwargs.setdefault("min_aligned_sessions", 3)
    return compare_adjusted_close_sources(
        a, b, asset_code="510300", left_source="EfinanceFetcher",
        right_source="BaostockFetcher", **kwargs
    )


def test_identical_return_series_at_different_adjusted_price_scales():
    a = _series([100, 101, 103, 105, 104, 110])
    b = a * 2.0
    result = _compare(a, b)
    assert result.status == "CONSISTENT"
    assert result.reasons == ()
    assert result.aligned_sessions == 6
    assert result.comparable_daily_returns == 5
    assert result.overlap_coverage_pct == 100
    assert result.total_return_gap_pp == pytest.approx(0.0)
    assert result.p95_daily_return_gap_bps == pytest.approx(0.0)
    assert result.level_ratio_at_start == pytest.approx(0.5)
    assert result.to_dict()["status"] == "CONSISTENT"


def test_partial_internal_history_cannot_look_like_perfect_daily_match():
    a = _series([100, 101, 102, 103, 104, 105])
    b = a.drop(a.index[2])
    result = _compare(a, b, min_coverage_pct=99)
    assert result.status == "REVIEW"
    assert "missing_provider_sessions" in result.reasons
    assert result.missing_right_sessions == 1
    assert result.aligned_sessions == 5
    assert result.comparable_daily_returns == 3
    assert result.overlap_coverage_pct == pytest.approx(5 / 6 * 100)


def test_single_day_adjustment_mismatch_flags_extreme_gap():
    a = _series([100, 101, 102, 103, 104, 105])
    b = _series([100, 101, 102, 110, 111, 112])
    result = _compare(a, b, max_daily_gap_limit_bps=100)
    assert result.status == "REVIEW"
    assert "extreme_daily_return_gap" in result.reasons
    assert "total_return_disagreement" in result.reasons
    assert result.worst_gap_date == a.index[3].date().isoformat()
    assert result.worst_daily_return_gap_bps > 100


def test_small_nearby_price_rounding_stays_consistent_with_explicit_limits():
    a = _series([100, 102, 103, 104, 105, 108])
    b = _series([100, 102.001, 103.001, 104.001, 105.001, 108.001])
    r = _compare(a, b)
    assert r.status == "CONSISTENT"
    assert r.total_return_gap_pp < 0.01


def test_low_overlap_is_not_passed_even_with_identical_returns():
    a = _series([100, 101, 102, 103])
    b = a.copy()
    r = _compare(a, b, min_aligned_sessions=5)
    assert r.status == "REVIEW"
    assert "insufficient_aligned_sessions" in r.reasons


def test_overlap_window_uses_common_start_and_end():
    index = pd.bdate_range("2026-01-05", periods=8)
    a = _series([100, 101, 102, 103, 104, 105, 106], index[:7])
    b = _series([50, 50.5, 51, 51.5, 52, 52.5, 53], index[1:])
    # The overlap contains dates [1..6] with a different price progression.
    r = _compare(a, b)
    assert r.first_common_date == index[1].date().isoformat()
    assert r.last_common_date == index[6].date().isoformat()
    assert r.aligned_sessions == 6
    assert r.overlap_sessions == 6


@pytest.mark.parametrize("left,right", [
    (_series([100, 101, 102]), _series([100, 0, 102])),
    (_series([100, 101, 102]), _series([100, math.inf, 102])),
    (_series([100, 101, 102]), _series([100, math.nan, 102])),
    (_series([100, 101, 102]), _series([100, -1, 102])),
    (_series([100, 101, 102]), _series([100, 101, 102], pd.bdate_range("2026-01-05", periods=3)[::-1])),
    (_series([100, 101, 102]), pd.Series([100, 101, 102], index=[1, 2, 3])),
])
def test_invalid_prices_or_dates_fail_closed(left, right):
    with pytest.raises(ValueError):
        _compare(left, right)


def test_duplicate_dates_fail_closed():
    a = _series([100, 101, 102])
    b = pd.concat([a, a.iloc[:1]])
    with pytest.raises(ValueError, match="unique"):
        _compare(a, b)


def test_no_consecutive_shared_sessions_fails_closed():
    ix = pd.bdate_range("2026-01-05", periods=6)
    a = _series([100, 101, 102, 103], ix[[0, 2, 4, 5]])
    b = _series([100, 102, 104, 105], ix[[0, 1, 3, 5]])
    with pytest.raises(ValueError, match="consecutive"):
        _compare(a, b)


@pytest.mark.parametrize("options", [
    {"min_aligned_sessions": 2}, {"min_aligned_sessions": True},
    {"min_coverage_pct": 110}, {"min_coverage_pct": float("nan")},
    {"p95_daily_gap_limit_bps": -0.5}, {"total_return_gap_limit_pp": math.inf},
])
def test_invalid_thresholds_fail_closed(options):
    a = _series([100, 101, 102, 103])
    with pytest.raises(ValueError):
        _compare(a, a * 2, **options)
