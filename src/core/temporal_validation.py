"""Opt-in temporal validation for a fixed-parameter single-ETF/cash strategy.

Chronological expanding-window folds and a final untouched holdout. This is
NOT parameter optimization/training or a predictive edge significance test.
The strategy core sees only prices through each window's final close, and
comparison is restricted to that window's out-of-sample intervals.

A position carried across a window boundary is notionally entered at that
boundary and liquidated at the window's end for an independent fee-aware
return. The result is therefore NOT a continuous account equity curve.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any
import math

import pandas as pd

from src.core.etf_rotation import CASH, RotationParams, run_backtest
from src.core.random_benchmark import RandomBenchmarkResult
from src.core.rotation_timing_adapter import (
    _binary_asset_weight,
    evaluate_rotation_trade_timing,
)


@dataclass(frozen=True)
class TemporalWindow:
    label: str
    kind: str
    training_start: str
    training_end: str
    test_start_close: str
    test_end_close: str
    test_intervals: int
    status: str
    benchmark: RandomBenchmarkResult | None


@dataclass(frozen=True)
class TemporalValidationReport:
    asset_code: str
    mode: str
    training_policy: str
    split_index: int
    total_price_rows: int
    holdout_fraction: float
    fold_count: int
    evaluated_folds: int
    holdout_status: str
    windows: tuple[TemporalWindow, ...]


def _check_input(closes: pd.DataFrame, asset_code: str, params: RotationParams) -> None:
    if not isinstance(asset_code, str) or not asset_code.strip() or asset_code == CASH:
        raise ValueError("a nonblank risk asset is required")
    if not isinstance(params, RotationParams) or params.top_n != 1:
        raise ValueError("fixed single-asset RotationParams(top_n=1) required")
    if not isinstance(closes, pd.DataFrame) or closes.columns.has_duplicates or list(closes.columns) != [asset_code]:
        raise ValueError("a single-column close frame for the requested asset is required")
    if not isinstance(closes.index, pd.DatetimeIndex) or closes.index.tz is not None \
            or closes.index.hasnans or not closes.index.is_unique or not closes.index.is_monotonic_increasing \
            or any(closes.index != closes.index.normalize()):
        raise ValueError("prices need unique, ascending, normalized timezone-naive trading dates")
    if not pd.api.types.is_numeric_dtype(closes[asset_code]):
        raise ValueError("prices must be numeric")
    if any(not math.isfinite(float(x)) or float(x) <= 0 for x in closes[asset_code]):
        raise ValueError("prices must be finite and strictly positive without missing dates")


def _window(
    closes: pd.DataFrame,
    *,
    asset_code: str,
    params: RotationParams,
    start: int,
    end: int,
    label: str,
    kind: str,
    simulations: int,
    slippage_bps: float,
    seed: int,
) -> TemporalWindow:
    """Run genuine lagged rotation on data only up to the test window end."""
    prefix = closes.iloc[:end + 1]
    start_day = closes.index[start]
    end_day = closes.index[end]
    result = run_backtest(prefix, [asset_code], None, params)

    held = 0
    eligible_trades = []
    for trade in result.trades:
        if trade.exec_date > end_day:
            raise ValueError("strategy leaked an execution after test end")
        old = _binary_asset_weight(trade.from_weights, asset_code)
        new = _binary_asset_weight(trade.to_weights, asset_code)
        if old != held or new == old:
            raise ValueError("strategy's executed trade ledger is inconsistent")
        held = new
        if trade.exec_date > start_day and trade.exec_date < end_day:
            eligible_trades.append(trade)

    # Recover the exposure *at* the fold boundary: the last historical trade
    # at or before start_day, not the ending state after all in-window trades.
    initial = 0
    for trade in result.trades:
        if trade.exec_date <= start_day:
            initial = _binary_asset_weight(trade.to_weights, asset_code)
        else:
            break

    boundary_trades = []
    if initial:
        boundary_trades.append(SimpleNamespace(
            exec_date=start_day,
            from_weights={CASH: 1.0},
            to_weights={asset_code: 1.0},
        ))
    # A trade at test_end_close affects no observed test interval; terminal
    # liquidation is already charged by the benchmark's simulation kernel.
    boundary_trades.extend(eligible_trades)
    invested = initial or any(
        _binary_asset_weight(trade.to_weights, asset_code) == 1
        for trade in eligible_trades
    )
    benchmark = None
    status = "NO_LONG_EXPOSURE"
    if invested:
        benchmark = evaluate_rotation_trade_timing(
            tuple(closes.index[start:end + 1]),
            closes[asset_code].iloc[start:end + 1].tolist(),
            boundary_trades,
            asset_code=asset_code,
            simulations=simulations,
            fee_bps=params.cost_bps,
            slippage_bps=slippage_bps,
            seed=seed,
        )
        status = "EVALUATED" if benchmark.informative else "NONINFORMATIVE"

    return TemporalWindow(
        label=label,
        kind=kind,
        training_start=closes.index[0].date().isoformat(),
        training_end=start_day.date().isoformat(),
        test_start_close=start_day.date().isoformat(),
        test_end_close=end_day.date().isoformat(),
        test_intervals=end - start,
        status=status,
        benchmark=benchmark,
    )


def evaluate_temporal_holdout(
    closes: pd.DataFrame,
    *,
    asset_code: str,
    params: RotationParams,
    min_training_intervals: int = 180,
    holdout_fraction: float = 0.2,
    walk_forward_folds: int = 3,
    min_fold_intervals: int = 20,
    simulations: int = 500,
    slippage_bps: float = 0.0,
    seed: int = 42,
) -> TemporalValidationReport:
    """Expanding-history OOS slices followed by a strictly later holdout.

    Parameters are FIXED before examination. Each fold replays the existing
    causal rotation engine using only prices available through that fold end;
    later holdout data cannot influence earlier observations. The 'training'
    prefix only supplies momentum history and prior holdings; this function
    performs no fit, grid search, threshold tuning, or automatic promotion.

    Fold and holdout results are independent from-cash accounting windows
    with virtual opening/closing at the boundary. A NO_LONG_EXPOSURE window
    is reported explicitly without fabricating a Monte Carlo score.
    """
    _check_input(closes, asset_code, params)
    for value, name, lower in (
        (min_training_intervals, "min_training_intervals", 1),
        (walk_forward_folds, "walk_forward_folds", 1),
        (min_fold_intervals, "min_fold_intervals", 2),
        (simulations, "simulations", 1),
        (seed, "seed", None),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or (lower is not None and value < lower):
            raise ValueError(f"{name} must be a valid integer")
    if simulations > 10000:
        raise ValueError("simulations exceeds permitted maximum")
    if not isinstance(holdout_fraction, (int, float)) or isinstance(holdout_fraction, bool) \
            or not math.isfinite(holdout_fraction) or not 0.1 <= holdout_fraction <= 0.4:
        raise ValueError("holdout_fraction must be within 0.1 and 0.4")
    if isinstance(slippage_bps, bool) or not isinstance(slippage_bps, (int, float)) \
            or not math.isfinite(slippage_bps) or slippage_bps < 0 \
            or slippage_bps + params.cost_bps >= 10000:
        raise ValueError("invalid slippage/fee bps")
    if min_training_intervals < params.lookback_days + 10:
        raise ValueError("training prefix is too short for momentum and execution lag")

    intervals = len(closes) - 1
    holdout_start = intervals - max(min_fold_intervals, round(intervals * holdout_fraction))
    available = holdout_start - min_training_intervals
    if available < walk_forward_folds * min_fold_intervals:
        raise ValueError("insufficient data for non-overlapping folds plus untouched holdout")

    base, extra = divmod(available, walk_forward_folds)
    start = min_training_intervals
    windows = []
    for i in range(walk_forward_folds):
        duration = base + (1 if i < extra else 0)
        end = start + duration
        windows.append(_window(
            closes, asset_code=asset_code, params=params, start=start,
            end=end, label=f"fold_{i + 1}", kind="walk_forward",
            simulations=simulations, slippage_bps=slippage_bps, seed=seed + i,
        ))
        start = end
    if start != holdout_start:
        raise RuntimeError("fold boundary does not match holdout start")
    windows.append(_window(
        closes, asset_code=asset_code, params=params, start=holdout_start,
        end=intervals, label="final_holdout", kind="holdout",
        simulations=simulations, slippage_bps=slippage_bps,
        seed=seed + walk_forward_folds,
    ))
    return TemporalValidationReport(
        asset_code=asset_code,
        mode="expanding_history_fixed_parameters",
        training_policy="no_optimization",
        split_index=holdout_start,
        total_price_rows=len(closes),
        holdout_fraction=holdout_fraction,
        fold_count=walk_forward_folds,
        evaluated_folds=sum(w.status == "EVALUATED" for w in windows[:-1]),
        holdout_status=windows[-1].status,
        windows=tuple(windows),
    )
