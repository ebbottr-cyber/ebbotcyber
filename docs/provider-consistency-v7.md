# EBBot V7 — ETF price-provider reconciliation

The two real-data smoke runs on 18 November 2026 produced slightly different
**observed net strategy** returns for ETF `510300`:
- BaostockFetcher: about 12.9762%, in a 100-random-schedule run.
- EfinanceFetcher: about 13.1843%, in a 4,000-schedule run.

**Those two executions are not a controlled price-provider comparison.**
They occurred at different times, and historical adjustment revisions, coverage
and market-data updates can differ. The new diagnostic compares both vendors
within **one job and one as-of date**.

## Research-only diagnostic

- `src/core/provider_consistency.py` compares *aligned daily returns*
  rather than nominal forward-adjusted close prices, which may legitimately
  differ by constant multiplicative scale.
- It checks date ordering, positivity/finite numeric closes, common coverage,
  missing sessions, observed cumulative return discrepancy, and median/95th/
  maximum absolute differences in **daily** close-to-close returns.
- Gaps in either provider are **not forward-filled** or treated as a
  same-day return; no accidental bridge over missing quote dates.
- Default `REVIEW` thresholds are exploratory (not mathematically proven
  universal): fewer than 120 matched sessions, below 99% overlap coverage,
  >15 bp 95th-percentile daily return difference, >150 bp worst daily gap,
  or >1 percentage point cumulative return difference.
- The diagnostic never auto-selects the provider with the best profits.
- `scripts/smoke_etf_provider_consistency.py` independently requests
  forward-adjusted ETF `510300` from **EfinanceFetcher** and
  **BaostockFetcher**, using the repository's existing ETF service and trading
  calendar. It refuses fallback substitution, data-quality warnings and
  missing/suspicious history. Both providers must return actual data.
- The smoke also independently estimates each provider's single-ETF/cash
  strategy result with identical strategy settings and random seed;
  the difference is described, never sent to strategy or execution code.

```bash
python -m pytest -q tests/test_provider_consistency.py
PYTHONPATH=. python scripts/smoke_etf_provider_consistency.py
```

The live smoke is network-dependent and should be reported as **BLOCKED**
when providers fail. `REVIEW` means the prices disagree beyond the stated
limits, not that a specific provider is fraudulent or that the strategy fails.
Only `CONSISTENT` means these *specific historical series* passed the
provisional comparison, not that the strategy has an edge.

No trades are placed, no credentials are requested, and no changes are made
to the production ETF rotation provider fallback, risk control, or UI. This
change is stacked on the draft Strategy Success Lab PR series; do **not**
merge it until full CI, provider reconciliation, independent review and
deployment smoke are satisfactory.
