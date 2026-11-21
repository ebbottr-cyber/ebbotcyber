# Single-asset ETF rotation — random timing research adapter

This opt-in adapter connects the actual ETF rotation backtest and its historical **executed trade ledger** to the read-only random-timing benchmark defined in [random-benchmark.md](random-benchmark.md).

It does **not** change ETF signals, the normal rotation report, DecisionSignal, Agent weights, market providers, scheduled runs, the API, the Web UI, or any order execution behavior.

## Run against already validated, adjusted historical ETF prices

```python
from src.core.etf_rotation import RotationParams
from src.core.rotation_timing_adapter import evaluate_single_asset_rotation_history

# df: previously loaded, date-indexed DataFrame of adjusted daily closes
# for one risk ETF, for example "510300"; source is outside this adapter.
report = evaluate_single_asset_rotation_history(
    df,
    asset_code="510300",
    params=RotationParams(
        lookback_days=60,
        rebalance="weekly",
        top_n=1,
        cost_bps=10,
    ),
    simulations=4000,
    slippage_bps=5,
    seed=42,
)
print(report)
```

The adapter calls the repository's existing `run_backtest` engine with this single risk ETF and **no safe asset**. It then interprets the engine's executed `Trade.exec_date`, `from_weights` and `to_weights`: a close-time entry earns returns only over the following close-to-close interval. The analysis window starts on the **first possible lagged execution close after a lookback-valid rebalance date**, not at the first profitable buy.

Only binary **100% risk asset / 100% cash** exposure is supported. Missing/duplicate dates, nonpositive or nonfinite prices, partial/multi-asset allocations, inconsistent trade ledgers and unjustified last-close buys fail explicitly. All-cash series without a long position are not benchmarkable, and return a validation error.

A lower-level `evaluate_rotation_trade_timing(dates, closes, trades, asset_code=...)` adapter is also provided for already generated ETF rotation trade ledgers. Supply the same **tradable evaluation date window**, after removing the momentum warm-up: passing prices from the training/warm-up portion would let randomized entries trade before the strategy was eligible.

## Interpretation and limitations

- Each randomized schedule matches the number of long spells, their individual durations (kept in original order), total invested bar count, and per-side fee plus slippage assumptions.
- The rotation strategy is rerun **with the same historical prices** for observation only; no live or predictive inference.
- The benchmark **independently** applies fees/slippage and forces liquidation at the last close. Its reported return can differ from the ETF backtest's own equity series, which uses turnover-based costs, a different display baseline and no forced terminal liquidation. Do not label them equal or compare their numbers without reconciling conventions.
- This does not benchmark the **multi-asset** ETF rotation portfolio, defensive safe-asset substitutions, dividend/cash yield, taxes, or stop-loss/limit-order fills.
- A favorable fraction of random returns beaten is descriptive, **not evidence of causal alpha, a calibrated p-value, or a profitable future strategy**. Validate across market regimes, walk-forward and holdout samples, plus risk-adjusted buy-and-hold.
- It relies on complete forward-adjusted daily closes supplied by an existing data pipeline; this adapter does not fetch or repair data.

## Checks

```bash
python -m pytest tests/test_random_benchmark.py tests/test_rotation_timing_adapter.py
python -m py_compile src/core/random_benchmark.py src/core/rotation_timing_adapter.py
```

The integration tests call the real single-asset ETF rotation engine with synthetic historical prices. The tests remain offline and never place orders.
