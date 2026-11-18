# Random timing benchmark (research only)

`src/core/random_benchmark.py` is an opt-in, deterministic, read-only baseline for evaluating long/cash market timing. It is **not** connected to DecisionSignal, the strategy aggregator, risk overrides, scheduler, order execution, APIs, or Web UI. A failure here cannot change live trade decisions.

## Inputs and interpretation

- `closes`: at least three positive, finite close prices, in chronological order, with **consistent adjusted/unadjusted price conventions**.
- `positions`: a 0/1 exposure flag for each *following* close-to-close interval: `positions[i]` applies to `closes[i] -> closes[i+1]`. Generate signals using only information available at or before `closes[i]`; do not feed same-bar hindsight signals.
- `simulations`: independent seeded draws, 1–10,000 (default 4,000); `seed` defaults to 42.
- `fee_bps` and `slippage_bps`: nonnegative cost in basis points **per side**, charged on every entry, every exit, and final liquidation. No leverage, borrow fee, taxes, dividends or cash yield are modeled.

```python
from src.core.random_benchmark import evaluate_random_benchmark

report = evaluate_random_benchmark(
    closes=[100, 103, 102, 104, 105, 107],
    positions=[0, 1, 1, 0, 1],
    simulations=4000,
    fee_bps=10,
    slippage_bps=5,
    seed=42,
)
print(report)
```

Random schedules preserve the original **number of long spells**, the **duration of each spell** (in its original order), the **number of invested bars**, and the **same price series and costs**. They redistribute cash gaps uniformly across permissible non-overlapping placements; there must be at least one cash bar between spells. These are random **entry timings**, not random stock picks and not bootstrap resampling of returns.

`fraction_random_at_least_observed` is the fraction of simulations whose net return equals or beats the strategy. **This is a descriptive Monte Carlo rank, not a validated p-value or proof of predictive edge.** Use `distinct_random_schedules` and `informative` to identify weak or degenerate timing universes. The result also includes net buy-and-hold return, median random net return, 5th/95th percentile, and max drawdown comparisons. When periods overlap or positions were optimized on the same history, out-of-sample evidence is required.

## Boundaries and next steps

- Deliberately separate from the existing `src/core/backtest_engine.py` daily-bar outcomes and not comparable to its stop-loss/take-profit semantics.
- Validate the source data and corporate actions first; run walk-forward and holdout tests, then paper trading, before considering any signal or strategy weight integration.
- Do not conclude a model is good from one favorable benchmark: compare with buy-and-hold, suitable risk-controlled baselines, and alternate market regimes. Extend to portfolio/multi-asset and more realistic execution costs in a later version.

Local check: `python -m unittest tests.test_random_benchmark` (or `python -m pytest tests/test_random_benchmark.py`).
