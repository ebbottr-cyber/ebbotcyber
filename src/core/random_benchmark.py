"""Read-only, reproducible random timing benchmark for long/cash strategies.

A position at index i is exposure over close[i] -> close[i + 1].
The benchmark preserves each long spell's duration (in its original order),
number of entries and total exposure, while randomizing the cash gaps.
It does not fetch market data, place orders, or adjust strategy weights.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from statistics import median
from typing import Sequence


@dataclass(frozen=True)
class RandomBenchmarkResult:
    observed_return_pct: float
    observed_max_drawdown_pct: float
    random_median_return_pct: float
    random_p05_return_pct: float
    random_p95_return_pct: float
    random_median_max_drawdown_pct: float
    fraction_random_at_least_observed: float
    buy_and_hold_return_pct: float
    entry_count: int
    exposure_bars: int
    total_bars: int
    simulations: int
    distinct_random_schedules: int
    informative: bool
    seed: int


def _long_spells(positions: Sequence[int]) -> list[int]:
    spells = []
    run = 0
    for position in positions:
        if position:
            run += 1
        elif run:
            spells.append(run)
            run = 0
    if run:
        spells.append(run)
    return spells


def _random_schedule(length: int, spells: Sequence[int], rng: random.Random) -> tuple[int, ...]:
    """Uniformly sample nonnegative external gaps and >=1-bar internal gaps."""
    k = len(spells)
    spare_cash = length - sum(spells) - (k - 1)
    # Stars and bars: a uniform composition of spare_cash into k+1 gaps.
    cuts = sorted(rng.sample(range(1, spare_cash + k + 1), k))
    walls = [0, *cuts, spare_cash + k + 1]
    gaps = [walls[i + 1] - walls[i] - 1 for i in range(k + 1)]
    schedule = [0] * gaps[0]
    for i, duration in enumerate(spells):
        schedule.extend([1] * duration)
        schedule.extend([0] * (gaps[i + 1] + (1 if i < k - 1 else 0)))
    if len(schedule) != length:
        raise RuntimeError("random schedule length mismatch")
    return tuple(schedule)


def _simulate(closes: Sequence[float], positions: Sequence[int], cost_rate: float) -> tuple[float, float]:
    equity = 1.0
    peak = 1.0
    worst_drawdown = 0.0
    previous = 0
    for i, position in enumerate(positions):
        if position != previous:
            equity *= 1.0 - cost_rate
        if position:
            equity *= closes[i + 1] / closes[i]
        peak = max(peak, equity)
        worst_drawdown = max(worst_drawdown, (peak - equity) / peak)
        previous = position
    if previous:
        equity *= 1.0 - cost_rate  # force liquidation at the last close
        worst_drawdown = max(worst_drawdown, (peak - equity) / peak)
    return (equity - 1.0) * 100.0, worst_drawdown * 100.0


def _percentile(sorted_values: Sequence[float], p: float) -> float:
    index = p * (len(sorted_values) - 1)
    lo = math.floor(index)
    hi = math.ceil(index)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (index - lo)


def evaluate_random_benchmark(
    closes: Sequence[float],
    positions: Sequence[int | bool],
    *,
    simulations: int = 4000,
    fee_bps: float = 0.0,
    slippage_bps: float = 0.0,
    seed: int = 42,
) -> RandomBenchmarkResult:
    """Compare long/cash timing against random timing, never generating trade advice.

    positions are *already decided* exposure flags, not same-bar signals;
    callers must lag signal generation to avoid look-ahead. Each transition
    (including final liquidation) pays fee_bps + slippage_bps per side.
    Results are descriptive, not a proof of statistical significance.
    """
    if isinstance(simulations, bool) or not isinstance(simulations, int) or not 1 <= simulations <= 10000:
        raise ValueError("simulations must be an integer between 1 and 10000")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    if len(closes) < 3 or len(positions) != len(closes) - 1:
        raise ValueError("requires >=3 closes and exactly one position per price interval")
    if any(isinstance(price, bool) or not isinstance(price, (int, float)) or
           not math.isfinite(price) or price <= 0 for price in closes):
        raise ValueError("close prices must be finite positive numbers")
    if any(type(pos) not in (bool, int) or pos not in (0, 1) for pos in positions):
        raise ValueError("positions must contain only 0/1 or booleans")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0
           for v in (fee_bps, slippage_bps)) or fee_bps + slippage_bps >= 10000:
        raise ValueError("costs must be nonnegative finite basis points with total <10000")

    schedule = tuple(int(pos) for pos in positions)
    spells = _long_spells(schedule)
    if not spells:
        raise ValueError("at least one long position is required")
    cost_rate = (fee_bps + slippage_bps) / 10000.0
    observed_return, observed_dd = _simulate(closes, schedule, cost_rate)
    rng = random.Random(seed)
    returns = []
    drawdowns = []
    distinct = set()
    for _ in range(simulations):
        randomized = _random_schedule(len(schedule), spells, rng)
        distinct.add(randomized)
        simulated_return, simulated_dd = _simulate(closes, randomized, cost_rate)
        returns.append(simulated_return)
        drawdowns.append(simulated_dd)
    returns.sort()
    buy_hold_return, _ = _simulate(closes, (1,) * len(schedule), cost_rate)
    # Informative only if there is more than one *possible* timing arrangement.
    # Stars-and-bars count: comb(number_of_cash_bars + 1, number_of_spells).
    cash_bars = len(schedule) - sum(spells)
    informative = math.comb(cash_bars + 1, len(spells)) > 1
    return RandomBenchmarkResult(
        observed_return_pct=observed_return,
        observed_max_drawdown_pct=observed_dd,
        random_median_return_pct=median(returns),
        random_p05_return_pct=_percentile(returns, 0.05),
        random_p95_return_pct=_percentile(returns, 0.95),
        random_median_max_drawdown_pct=median(drawdowns),
        fraction_random_at_least_observed=sum(v >= observed_return for v in returns) / simulations,
        buy_and_hold_return_pct=buy_hold_return,
        entry_count=len(spells),
        exposure_bars=sum(spells),
        total_bars=len(schedule),
        simulations=simulations,
        distinct_random_schedules=len(distinct),
        informative=informative,
        seed=seed,
    )
