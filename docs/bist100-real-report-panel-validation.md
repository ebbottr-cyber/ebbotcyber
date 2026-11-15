# BIST100 historical real-report-to-panel proof (one-time integration)

## Grounded source

The data is the **actual 100-stock historical Yahoo Finance technical report** produced by an isolated GitHub runner in Draft PR #8. It is not fabricated from one-stock fixtures or a network-free synthetic candle series.

- Earlier passing Actions run: https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/43723300907
- Artifact name: `bist100-real-yahoo-100-43723300907`
- Technical report inside ZIP: `bist100-live-100-43723300907-1/technical-100.json`
- Exact technical JSON SHA-256: `42a0834b5633b9667979966acc847fde6f431fb8f57ced16c432161fb287b06a`
- Report `as_of=2026-11-15`, exchange session `2026-11-13`, `checked=100`, `analyzed=100`, `watchlist_eligible=97`, `remaining=0`. Historical data only.

## Verification stages (integration draft PR)

The separate workflow job `bist100-real-report-panel-e2e` is scoped to draft branch `integration/bist100-panel-real-report`.

1. Download the **existing artifact** with a limited GitHub Actions `actions:read` token from the same repository. Require exactly one `technical-100.json` and byte-for-byte SHA-256 identity. Fail closed if missing or mismatched; never replace it with example stock data.
2. Run the real JSON through the **existing server-side validator**, including membership, ranks, status counts, prices, risk flags, exact previous XIST session, and `as_of` date. Demand 100/100 validated.
3. Run the actual TypeScript `parseBist100TechnicalReport` and pure `selectBist100Ranking` functions against **all 100 real rows**, asserting original rank order, ticker/score search, 97/3 MA5 distance split, RSI, MACD and unchanged source counters.
4. Mount the real `Bist100TechnicalPanel` React component with its API mocked to return that fully validated, historical report, verifying DOM presentation, pagination, symbol search, 80+ score filter and three MA5 warning rows.

This is a **historical admin-panel contract and DOM test**, not a live deployed browser, production report publication, full seven-market analysis, or investment recommendation. It sends **no orders**, writes **no SQLite**, calls **no LLM**, and does not download new price data.

## Historical artifact retention

The original GitHub artifact had a **7-day retention**. This time-boxed CI proof is designed for a single draft integration run while that artifact exists. Future reruns **must fail** when the artifact is missing, rather than quietly assert synthetic 100/100 success. A long-lived test should separately record a provenance-verified snapshot (with source licensing reviewed) or explicitly regenerate and revalidate a new as-of historical report. **Do not run this artifact-dependent E2E job as a permanent default PR gate.**

Earlier PR #14 already passed its standard TypeScript, Vitest, ESLint, build and Python backend checks; this new job is an *additional* proof that connects them to the real historical report.
