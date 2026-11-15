# Six-market historical smoke: approved, read-only admin report

**Purpose:** The seven-market Data Center no longer needs the user to select
the six-market JSON file every time. When the operator *explicitly configures*
a previously verified one-symbol-per-market Yahoo smoke report on the server,
the dashboard reads it through a protected **GET-only** endpoint.

The scope **never changes**: China (600519.SS), Hong Kong (0700.HK),
US (AAPL), Japan (7203.T), South Korea (005930.KS), Taiwan (2330.TW).
These are **six example stocks, not six complete equity universes**.
The separately authenticated BIST100 panel can show a historical 100-stock
technical report; that does not imply seven live exchange integrations.

## Approval and setup

1. Obtain the historical `six-market-yahoo-smoke-*.json` from the previously
   verified GitHub Actions run (e.g. green PR #9/#11) or a separately
   approved read-only smoke run. Note the actual `as_of` date, historical
   exchange sessions, expected currencies, all per-market statuses.
2. Check the file's source and integrity **outside the application**.
   Compute a SHA-256 for the JSON *file itself*, not for any artifact ZIP.
   Keep the report under an existing read-only directory on the backend.
   Do not publish the original report or any license-restricted payload.
3. Only after operator approval, configure both environment variables
   on the backend (not in Git):
   - `SIX_MARKET_SMOKE_REPORT_PATH`: absolute existing regular JSON path,
     no file symlink and no symlink anywhere in its parent chain.
   - `SIX_MARKET_SMOKE_REPORT_SHA256`: exact SHA-256 hex digest of the
     approved bytes.
4. With admin authentication enabled, the browser requests
   `GET /api/v1/data/six-market/smoke-report`, with `Cache-Control:
   no-store, private` and `X-Content-Type-Options: nosniff`.
   The route never accepts a caller-supplied `path`, never uploads JSON,
   and cannot run Yahoo probes.
5. The backend checks all six example identities/currencies, reported
   status/counts, dates, history length and score, plus an **independently
   computed last completed exchange session** for every recorded session.
   Hash mismatch, malformed JSON, fake successes or missing calendars
   result in 422. Missing/unapproved files return 404; missing login returns
   401; disabled authentication returns 404.
6. The panel automatically shows the dated saved evidence if available;
   otherwise it shows **no evidence**, never six verified markets.
   Users may still select a browser-local historical JSON as a fallback;
   a local file takes precedence until they explicitly reload the server
   version. That browser-only choice cannot independently prove market-data
   provenance or the true exchange calendar.

**Operator verification is required:** a matching digest verifies the file
against the operator-approved fingerprint, not independent authenticity
of the data originating from Yahoo. Each calendar check validates the
historical *as-of* session, **not** today's quote freshness. The UI
explicitly labels every result as historical. Failure statuses stay visible
and are never converted into successful analyses.

## No-write boundary and tests

`src/services/six_market_smoke_report_reader.py` is strictly read-only.
It does not import from the network, trade, open SQLite, request paid AI,
run schedules, change the runtime configuration or create destination files.
The existing `src.services.six_market_live_smoke` producer remains a
separate explicit tool. This feature does not add a write/upload endpoint
or publish an actual report to any deployment.

`tests/test_six_market_smoke_report_reader.py` tests valid/partial
reports, hash mismatch, symlinked sources/ancestors, wrong scope/currency/
symbols, fabricated stale sessions, missing calendar, authorization,
caller path injection and 404/422 behavior. The frontend Vitest/DOM tests
cover the approved server read and no-evidence fallback.

**Release status:** Draft PR #21, stacked on PR #20, with no merge or
production configuration; wait for exact-head CI and manual approval.
