# Strategy Success Lab V8 — Fixed-parameter chronological validation

V8 adds a **read-only**, retrospective, explicitly **fixed-parameter**
walk-forward-style evaluation with a final reserved chronological holdout.
It does not train machine-learning models, select parameters, change live
strategies, or promote a strategy to paper/live trading.

## What the temporal split actually tests

1. Consume only independently validated, forward-adjusted daily close prices
   in trading-date order from one ETF. Confirm source and missing dates first.
2. Reserve the last 20% of daily price intervals as a **final holdout**.
   No strategy settings are chosen by inspecting this final period.
3. Divide the pre-holdout intervals after an initial 180-day history into
   three consecutive non-overlapping walk-forward evaluation windows. Each
   later window has a longer historical context available for momentum.
4. For each test window run the **actual** existing
   `src.core.etf_rotation.run_backtest` on a **truncated price frame ending
   at that window's final close**. Future bars are not passed to the engine.
   Signals are generated with the engine's existing next-session execution lag.
5. Convert its recorded historical executed ETF trades into the original
   `evaluate_rotation_trade_timing` benchmark. Randomize timing **inside
   each test window only**, preserving trade lengths/count, accounting
   fees/slippage on every side and forced end-of-window liquidation.
6. Record all folds, even those with no long exposure or without meaningful
   random timing alternatives. Never silently discard a failed period.

Because the fixed rule needs prior bars for its momentum lookback, the
"training" history supplies indicator warm-up and previously held position;
**no learning/fitting, optimization, or parameter selection is done**. This
is strictly expanding-history *out-of-sample reporting*, not nested
cross-validation or proof that selected parameters generalize.

## Boundary accounting

At the beginning of each test interval, a portfolio that was already holding
the ETF in the warm-up is treated as **a fresh virtual entry** at the test
boundary. The last held position is **virtually liquidated** at the final
test close. This is appropriate for independent random timing comparison
windows but means the per-fold net returns **do not constitute the exact
continuous funded account P&L** and cannot simply be chained together.
Trade executions on the test period's final close do not have a subsequent
exposure interval, and thus are not counted as test entries.

These rules also mean that a fold with uninterrupted exposure has **only one
feasible timing arrangement**; `NONINFORMATIVE` is the correct outcome,
not a favorable test result. `NO_LONG_EXPOSURE` is likewise reported
without pretending to calculate randomized timing statistics.

## Usage (offline, no orders)

```python
from src.core.etf_rotation import RotationParams
from src.core.temporal_validation import evaluate_temporal_holdout

# etf_closes: validated, date-indexed one-column adjusted daily price frame
result = evaluate_temporal_holdout(
    etf_closes,
    asset_code="510300",
    params=RotationParams(
        lookback_days=40, rebalance="weekly",
        top_n=1, switch_buffer_pct=2, cost_bps=10,
    ),
    min_training_intervals=180,
    walk_forward_folds=3,
    holdout_fraction=0.20,
    min_fold_intervals=30,
    simulations=500,
    slippage_bps=0,
    seed=42,
)
for window in result.windows:
    print(window.label, window.status, window.benchmark)
```

For an external-data smoke with existing market-data providers:

```bash
PYTHONPATH=. python scripts/smoke_strategy_lab_temporal.py
```

A real smoke is `PASS` only when the final holdout and at least two folds
have informative randomized timing comparisons. A `NOT_EVALUABLE` response
signals weak or missing evidence; a provider timeout, unadjusted/missing
quotes or a bad split reports `BLOCKED`. Neither outcome means to buy/sell.

## Limits and release safety

- A historical adjusted price dataset is **not guaranteed to be
  point-in-time**, so later corporate-action revisions could still leak into
  older adjusted close levels. This v1 does not validate point-in-time
  provider vintages or dividend/cash-yield treatment.
- The fixed parameter rule was already explored on earlier histories.
  We cannot honestly call this untouched data an independent external holdout
  unless the selection and iteration history is documented and frozen before
  its evaluation. Prefer **prospective paper trading** to assess future edge.
- Monte Carlo rank is a descriptive timing comparison, not a calibrated
  significance test or statistically independent observation across folds.
- No portfolio multi-asset or Solana/crypto support. No leverage, taxes,
  market impact, or live execution fills.
- No API/UI wiring and no production order, agent, scheduling, training or
  strategy configuration paths are changed. Parent PRs #30/#32/#34/#37/#42
  are still unmerged; this is another stacked draft.

Verification: `python -m pytest -q tests/test_temporal_validation.py`
and GitHub Actions on this branch. All tests must be green and independently
reviewed before any merge. Non-English companion version is not provided for
this research-only internal technical specification.
