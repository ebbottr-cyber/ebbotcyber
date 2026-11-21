# Strategy Success Lab (research-only UI)

This stacked change depends on the read-only random timing engine (PR #30) and
the executed-trade ETF adapter (PR #32). It adds a **manually triggered,
research-only** analysis of one eligible ETF from the configured rotation pool.

## Web
- New `/strategy-lab` route and sidebar navigation in Turkish, English and Chinese.
- The panel loads the configured six-digit ETF symbols and does **not** run any
  computation on page load. User must select an ETF and click Compare.
- Results show strategy, median randomized and buy-and-hold returns, return
  percentiles, maximum drawdowns, exposures, distinct random timing samples and
  the historical data source. Missing/invalid data is an error, not a zero return.
- Stale asynchronous responses are ignored when selections change or the page
  unmounts. No invented placeholder performance values are shown.

## API
- `GET /api/v1/strategy-lab/etfs`: read-only list of configured six-digit ETF
  codes (does not fetch market data).
- `POST /api/v1/strategy-lab/etf` body:
  `{"asset_code":"510300","simulations":500}`. The code must appear in the
  configured ETF rotation pool. 100–4000 randomized samples are allowed.
- Uses the same existing forward-adjusted-price ETF provider and CN trading
  calendar as ETF rotation; the years used are bounded to 1–5.
- Rejects incomplete/dirty price history and research periods with no long
  trade. The endpoint is covered by the existing optional admin-session
  middleware when `ADMIN_AUTH_ENABLED=true`.
- No database writes, scheduled jobs, broker/wallet connection, trade execution,
  strategy weight modification or LLM calls. Requests can still trigger a
  provider fetch; run only when needed. The global authentication setting
  remains relevant, particularly on public deployments.

## Comparison semantics
The existing ETF rotation strategy runs with one risk ETF and cash (no safe ETF);
its close-executed historical trades are mapped to the next price interval.
Fees are inherited from the rotation config and terminal liquidation is
recalculated in the research benchmark; a **0 bp slippage assumption** is
reported explicitly, not implied to be realistic. The service does **not**
claim its return reproduces the historical rotation equity curve. Random
samples preserve trade count, ordered holding spells, and time in market.

The reported `fraction_random_at_least_observed` is only a **descriptive
empirical rank**, not a calibrated p-value. Buy-and-hold and risk metrics are
shown to discourage judging a system by absolute profits alone.

## Tests

```bash
python -m pytest tests/test_random_benchmark.py tests/test_rotation_timing_adapter.py tests/test_strategy_lab_service.py
cd apps/dsa-web
npm ci
npx vitest run src/pages/__tests__/StrategyLabPage.test.tsx
npm run build
```

## Stacked-branch targeted CI

PR #34 targets the PR #32 feature branch. For that reason, the main-only
`pr1-verify.yml` workflow does not run automatically here. The base branch
now also contains `.github/workflows/strategy-lab-targeted.yml`, which
checks only the related Python unit/integration tests, the new React page
tests, and TypeScript typecheck. This workflow is **not a substitute** for
the complete repository CI once rebased to `main`.

## Known dependencies and limits
- PR #30 is not merged and the full pipeline has pre-existing unrelated
  failures involving missing workflow/.env files and Turkish localization;
  **do not claim production readiness while CI is red**.
- PR #32 is also not merged and has limited offline verification.
- This initial lab deliberately excludes multi-asset strategies, crypto,
  derivatives, risk-adjusted portfolio baselines, and automated strategy
  promotion. Add these only after the restricted single-ETF use case passes
  reproducible end-to-end tests.
- No screenshot or running UI is attached yet: the current environment has no
  running EBBot web server or authenticated historical data source. Visual
  verification must be supplied before making this PR ready for merge.
