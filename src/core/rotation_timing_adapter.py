"""Read-only bridge from an ETF rotation trade ledger to random timing research.

Consumes already calculated close-executed rotation trades. It deliberately
cannot place orders, read accounts, or alter DecisionSignals and risk rules.
Only a single fully-invested risk asset or cash is accepted (no safe-asset leg).
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from src.core.random_benchmark import RandomBenchmarkResult, evaluate_random_benchmark


CASH = "CASH"


def _binary_asset_weight(weights: Mapping[str, float], asset_code: str) -> int:
    """Accept only 100% single-asset exposure or 100% cash; fail closed."""
    if not isinstance(weights, Mapping) or not weights:
        raise ValueError("trade weights must be a nonempty mapping")
    if any(code not in {asset_code, CASH} for code in weights):
        raise ValueError("multi-asset or safe-asset allocations are unsupported")
    values = []
    for weight in weights.values():
        if isinstance(weight, bool) or not isinstance(weight, (int, float)) or not math.isfinite(weight):
            raise ValueError("weights must be finite numeric values")
        if weight < 0 or weight > 1:
            raise ValueError("weights must be within [0, 1]")
        values.append(weight)
    if not math.isclose(sum(values), 1.0, rel_tol=0, abs_tol=1e-9):
        raise ValueError("trade weights must sum to one")
    exposure = float(weights.get(asset_code, 0))
    if math.isclose(exposure, 1.0, rel_tol=0, abs_tol=1e-9):
        return 1
    if math.isclose(exposure, 0.0, rel_tol=0, abs_tol=1e-9):
        return 0
    raise ValueError("partial exposure is unsupported")


def evaluate_rotation_trade_timing(
    dates: Sequence[Any],
    closes: Sequence[float],
    trades: Sequence[Any],
    *,
    asset_code: str,
    simulations: int = 4000,
    fee_bps: float = 0.0,
    slippage_bps: float = 0.0,
    seed: int = 42,
) -> RandomBenchmarkResult:
    """Benchmark the historical single-asset rotation ledger against random timing.

    Each trade is an existing ETF rotation Trade object: exec_date,
    from_weights and to_weights. Execution at close[i] sets exposure over
    close[i] -> close[i+1]. Pass tradable evaluation dates only, excluding
    strategy lookback/warmup and any ineligible or stale price history.

    All trades must fall inside the window, starting from all-cash. Rejects
    incomplete ledgers, duplicate/out-of-order trading dates, weight changes
    that cannot be represented by binary exposure, and final-close entries.
    Per-side fees/slippage are recalculated for all schedules and the final
    position is liquidated; this is not a reproduction of the ETF equity curve.
    """
    if not isinstance(asset_code, str) or not asset_code.strip() or asset_code == CASH:
        raise ValueError("asset_code must be a nonblank risk-asset symbol")
    if len(dates) != len(closes) or len(dates) < 3:
        raise ValueError("dates and closes must match, with at least three price rows")
    try:
        if any(a is None or b is None or not a < b for a, b in zip(dates, dates[1:])):
            raise ValueError("dates must be strictly increasing and unique")
        date_indexes = {day: i for i, day in enumerate(dates)}
    except (TypeError, ValueError) as exc:
        raise ValueError("dates must be comparable, unique and strictly increasing") from exc
    if len(date_indexes) != len(dates):
        raise ValueError("duplicate dates are not allowed")

    # Core validates all prices and costs. Validate trade mapping separately.
    changes = {}
    previous_exposure = 0
    last_index = -1
    for trade in trades:
        try:
            index = date_indexes[trade.exec_date]
            from_weight = _binary_asset_weight(trade.from_weights, asset_code)
            to_weight = _binary_asset_weight(trade.to_weights, asset_code)
        except (AttributeError, KeyError, TypeError) as exc:
            raise ValueError("trade execution date or weight data is missing") from exc
        if index <= last_index:
            raise ValueError("trades must be ordered by unique execution dates")
        if index == len(dates) - 1 and to_weight == 1:
            raise ValueError("final-close entry has no observable exposure interval")
        if from_weight != previous_exposure:
            raise ValueError("trade ledger has a missing or inconsistent position transition")
        if to_weight == from_weight:
            raise ValueError("no-op trades cannot be represented as position transitions")
        changes[index] = to_weight
        previous_exposure = to_weight
        last_index = index

    positions = []
    current = 0
    for index in range(len(dates) - 1):
        if index in changes:
            current = changes[index]
        positions.append(current)
    return evaluate_random_benchmark(
        closes,
        positions,
        simulations=simulations,
        fee_bps=fee_bps,
        slippage_bps=slippage_bps,
        seed=seed,
    )


def evaluate_single_asset_rotation_history(
    closes: Any,
    *,
    asset_code: str,
    params: Any,
    simulations: int = 4000,
    slippage_bps: float = 0.0,
    seed: int = 42,
) -> RandomBenchmarkResult:
    """Research-only evaluation using EBBot's existing single-asset ETF strategy.

    Runs the genuine lagged rotation backtest with 100% asset or 100% cash,
    then benchmarks its resulting trade ledger against randomized timings.
    Evaluation starts on the earliest possible next-close execution date
    after a lookback-valid weekly/monthly signal. This excludes warm-up data
    and does not condition the comparison window on the first profitable entry.

    No database, data-provider, signal, order, notification or runtime wiring.
    The benchmark return is independently recomputed with forced liquidation;
    it must not be mistaken for the rotation engine's reported equity curve.
    """
    import pandas as pd

    from src.core.etf_rotation import EXECUTION_LAG_DAYS, rebalance_dates, run_backtest

    if not isinstance(asset_code, str) or not asset_code.strip() or asset_code == CASH:
        raise ValueError("asset_code must be a nonblank risk-asset symbol")
    if not isinstance(closes, pd.DataFrame) or asset_code not in closes.columns:
        raise ValueError("closes must be a DataFrame containing the requested asset")
    if not isinstance(closes.index, pd.DatetimeIndex) or closes.index.hasnans or not closes.index.is_monotonic_increasing \
            or not closes.index.is_unique:
        raise ValueError("closes must have a strictly increasing unique DatetimeIndex")
    if closes.columns.has_duplicates:
        raise ValueError("duplicate asset columns are unsupported")
    if not pd.api.types.is_numeric_dtype(closes[asset_code]):
        raise ValueError("close prices must have numeric dtype")
    if params.top_n != 1 or params.lookback_days < 1:
        raise ValueError("requires top_n=1 and a positive lookback_days")
    if len(closes) < params.lookback_days + 4:
        raise ValueError("insufficient history after momentum lookback")
    raw = closes[[asset_code]]
    prices = raw[asset_code].tolist()
    if any(not isinstance(p, (int, float)) or not math.isfinite(p) or p <= 0 for p in prices):
        raise ValueError("close prices must be finite and positive with no missing rows")

    eligible_dates = closes.index[params.lookback_days:]
    signals = rebalance_dates(eligible_dates, params.rebalance)
    if not len(signals):
        raise ValueError("no eligible signal date")
    first_signal_idx = int(closes.index.get_loc(signals[0]))
    start_idx = first_signal_idx + EXECUTION_LAG_DAYS
    if len(closes) - start_idx < 3:
        raise ValueError("not enough executable intervals after first eligible signal")

    strategy = run_backtest(raw, [asset_code], None, params)
    return evaluate_rotation_trade_timing(
        tuple(closes.index[start_idx:]),
        prices[start_idx:],
        strategy.trades,
        asset_code=asset_code,
        simulations=simulations,
        fee_bps=params.cost_bps,
        slippage_bps=slippage_bps,
        seed=seed,
    )
