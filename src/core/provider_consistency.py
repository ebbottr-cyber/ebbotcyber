"""Read-only cross-provider quality diagnostics for adjusted ETF close series.

Compare **daily returns** on identical dates, not nominal price levels, since
two legitimate adjustment baselines can differ by a constant multiplicative
factor. Missing sessions, partial overlaps, inconsistent return histories, or
provider outages never imply financial alpha or a preferred market provider.
No feed/strategy/risk/decision/order code imports this module by default.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import math

import pandas as pd


@dataclass(frozen=True)
class ProviderConsistencyReport:
    asset_code: str
    left_source: str
    right_source: str
    first_common_date: str
    last_common_date: str
    overlap_sessions: int
    aligned_sessions: int
    comparable_daily_returns: int
    missing_left_sessions: int
    missing_right_sessions: int
    overlap_coverage_pct: float
    left_total_return_pct: float
    right_total_return_pct: float
    total_return_gap_pp: float
    median_daily_return_gap_bps: float
    p95_daily_return_gap_bps: float
    worst_daily_return_gap_bps: float
    worst_gap_date: str
    level_ratio_at_start: float
    status: str
    reasons: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


def _validate_series(series: pd.Series, name: str) -> pd.Series:
    if not isinstance(series, pd.Series) or len(series) < 2:
        raise ValueError(f"{name}: requires at least two observations")
    if not isinstance(series.index, pd.DatetimeIndex):
        raise ValueError(f"{name}: requires DatetimeIndex")
    if series.index.hasnans or not series.index.is_unique or not series.index.is_monotonic_increasing:
        raise ValueError(f"{name}: dates must be strictly increasing, unique and valid")
    if any(series.index != series.index.normalize()) or series.index.tz is not None:
        raise ValueError(f"{name}: requires timezone-naive normalized daily dates")
    if not pd.api.types.is_numeric_dtype(series):
        raise ValueError(f"{name}: close prices must be numeric")
    values = series.astype(float)
    if not all(math.isfinite(v) and v > 0 for v in values):
        raise ValueError(f"{name}: close prices must be finite and positive")
    return values


def compare_adjusted_close_sources(
    left: pd.Series,
    right: pd.Series,
    *,
    asset_code: str,
    left_source: str,
    right_source: str,
    min_aligned_sessions: int = 120,
    min_coverage_pct: float = 99.0,
    p95_daily_gap_limit_bps: float = 15.0,
    max_daily_gap_limit_bps: float = 150.0,
    total_return_gap_limit_pp: float = 1.0,
) -> ProviderConsistencyReport:
    """Return a diagnostic report, never a trading permission or statistical test.

    Assumes both series represent the *same ETF* and share forward-adjusted
    conventions (validated by the caller/provider). Actual calendars are
    verified upstream by the ETF rotation service. Compare on the exact
    intersecting dates and flag missing sessions inside the overlap window.

    A provider may revise its adjustment history; differences are reported,
    not silently "corrected" by selecting whichever yields better P&L.
    Thresholds are conservative research flags, not universal market rules.
    """
    if not isinstance(asset_code, str) or not asset_code.strip():
        raise ValueError("asset_code required")
    if not isinstance(left_source, str) or not left_source.strip() or not isinstance(right_source, str) or not right_source.strip() or left_source == right_source:
        raise ValueError("requires two distinct named providers")
    if isinstance(min_aligned_sessions, bool) or not isinstance(min_aligned_sessions, int) or min_aligned_sessions < 3:
        raise ValueError("min_aligned_sessions must be >= 3")
    for key, value in (
        ("min_coverage_pct", min_coverage_pct),
        ("p95_daily_gap_limit_bps", p95_daily_gap_limit_bps),
        ("max_daily_gap_limit_bps", max_daily_gap_limit_bps),
        ("total_return_gap_limit_pp", total_return_gap_limit_pp),
    ):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError(f"{key} must be nonnegative and finite")
    if min_coverage_pct > 100:
        raise ValueError("min_coverage_pct cannot exceed 100")

    a = _validate_series(left, left_source)
    b = _validate_series(right, right_source)
    start = max(a.index.min(), b.index.min())
    end = min(a.index.max(), b.index.max())
    if start >= end:
        raise ValueError("no multi-session date overlap")

    a = a.loc[start:end]
    b = b.loc[start:end]
    union = a.index.union(b.index).sort_values()
    paired = pd.concat({"left": a, "right": b}, axis=1).reindex(union)
    common = paired.dropna()
    if len(common) < 2:
        raise ValueError("not enough common observations")

    # Returns over adjoining union dates only: never skip a missing source
    # session to create an artificial multi-day 'daily' return.
    both_adjacent = paired.notna().all(axis=1) & paired.notna().all(axis=1).shift(1, fill_value=False)
    daily_diff = (paired["left"].pct_change(fill_method=None) -
                  paired["right"].pct_change(fill_method=None)).abs()[both_adjacent] * 10000.0
    if daily_diff.empty:
        raise ValueError("no comparable consecutive daily returns")

    total_left = (common["left"].iloc[-1] / common["left"].iloc[0] - 1.0) * 100
    total_right = (common["right"].iloc[-1] / common["right"].iloc[0] - 1.0) * 100
    coverage = len(common) / len(union) * 100
    p95 = float(daily_diff.quantile(0.95))
    max_gap = float(daily_diff.max())
    total_gap = abs(total_left - total_right)
    reasons: list[str] = []
    if len(common) < min_aligned_sessions:
        reasons.append("insufficient_aligned_sessions")
    if coverage < min_coverage_pct:
        reasons.append("missing_provider_sessions")
    if p95 > p95_daily_gap_limit_bps:
        reasons.append("p95_daily_return_gap")
    if max_gap > max_daily_gap_limit_bps:
        reasons.append("extreme_daily_return_gap")
    if total_gap > total_return_gap_limit_pp:
        reasons.append("total_return_disagreement")

    return ProviderConsistencyReport(
        asset_code=asset_code,
        left_source=left_source,
        right_source=right_source,
        first_common_date=common.index[0].date().isoformat(),
        last_common_date=common.index[-1].date().isoformat(),
        overlap_sessions=len(union),
        aligned_sessions=len(common),
        comparable_daily_returns=len(daily_diff),
        missing_left_sessions=int(paired["left"].isna().sum()),
        missing_right_sessions=int(paired["right"].isna().sum()),
        overlap_coverage_pct=coverage,
        left_total_return_pct=total_left,
        right_total_return_pct=total_right,
        total_return_gap_pp=total_gap,
        median_daily_return_gap_bps=float(daily_diff.median()),
        p95_daily_return_gap_bps=p95,
        worst_daily_return_gap_bps=max_gap,
        worst_gap_date=daily_diff.idxmax().date().isoformat(),
        level_ratio_at_start=float(common["left"].iloc[0] / common["right"].iloc[0]),
        status="REVIEW" if reasons else "CONSISTENT",
        reasons=tuple(reasons),
    )
