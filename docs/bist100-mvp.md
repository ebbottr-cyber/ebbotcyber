# BIST100 MVP — Phase 1

This is the isolated starting point for Turkish BIST100 support.

- Turkish equities use explicit `TICKER.IS` Yahoo Finance notation (e.g., `THYAO.IS`, `ASELS.IS`, `AKFYE.IS`); do **not** strip `.IS` or infer a Turkish market from a bare ticker.
- The `XU100.IS` BIST100 benchmark is an **index**, not the 101st stock.
- Syntax validation alone does **not** confirm BIST100 membership, actual quotes, liquidity, prices, or market hours.
- Before main analysis/screening use, add explicit `tr` routing, TRY currency, `Europe/Istanbul` time zone and source-quality data. Never fall back to Chinese A-share feeds on Yahoo quote failure.
- Build a **dated, source-verified membership snapshot** for the current Oct 1–Dec 31, 2026 index period. Borsa İstanbul’s quarterly changes are only **additions/removals**, not a complete roster; do not treat substitute stocks as current members. See https://www.borsaistanbul.com/en/announcement/15598/bist-stock-indices-periodic-review and https://www.borsaistanbul.com/en/index/xu100.
- The first commit contains only stand-alone symbol validation, offline tests, and this scope note. It does **not** connect the existing screens, provider, market context or production execution.

Track integration in the BIST100 MVP GitHub issue.

## Phase 2 — explicit routing contracts (candidate, not deployed)

- The `tr` market label is emitted only for valid, explicitly suffixed `.IS` equities; `XU100.IS` is not a constituent.
- BIST equity daily history is **Yahoo Finance only**. If Yahoo is missing or unavailable, report no data. Never fall back to AkShare, Efinance, mainland A-share or an unknown custom fetcher.
- The `XIST` exchange calendar in `exchange-calendars 4.13.3` uses `Europe/Istanbul`. Special trading half-days still require additional production validation.
- Not yet complete: live Yahoo Finance validation of all 100 constituents, web input, integrated 100-stock screener, TRY data-source metadata validation and quote staleness/coverage reporting.

## Phase 3 — date-bounded 100-member candidate snapshot

- `src/data/bist100_constituents_2026q4.json` stores the **100 unique members** for **2026-10-01 through 2026-12-31**, last independent list check `as_of=2026-11-08`, with provenance and source URLs. The snapshot was cross-checked 2026-11-15 against two independent full listings: https://bistsirketleri.com/bist-100-sirketleri/ and https://borsamorsa.com/bist-100-hisseleri/.
- Official Borsa İstanbul 2026-Q4 periodic review confirms the **27 additions, 27 exclusions and 3 substitute stocks**; it does not by itself publish all 100 active members in that delta table. Source: https://www.borsaistanbul.com/duyuru/15598/bist-pay-endeksleri-donemsel-degisiklikleri.
- `src/services/bist100_universe.py` is the offline, dependency-light loader. It refuses use outside the effective range, rejects duplicates/missing members/non-.IS codes, validates membership changes and sources, and returns symbols in canonical `.IS` Yahoo form. The benchmark `XU100.IS` is never a stock.
- `tests/test_bist100_universe.py` verifies counts, official additions/exclusions, substitutes, metadata, source provenance, and stale-period rejection.
- **Important release boundary:** This is a dated, source-cross-checked **candidate** roster, not a claim of independently fetched official full 100-member CSV, a live quote-coverage result, or permission to distribute exchange market data. Do not deploy or claim 100/100 analyzed until provider checks and a working screener/report exist.
- Separate CI baseline issues (`.github/workflows/*`, `.env.example`, Turkish notification text) remain outside this feature. Changes must stay on Draft PR #8, separate from Draft security PR #2 and unchanged `main`.

## Phase 4 — Historical Yahoo price coverage (offline-tested candidate)

- `src/services/bist100_coverage.py` audits the dated **100**-stock snapshot through the project's direct `yfinance` dependency **only**, without importing the eager `data_provider` package or invoking `DataFetcherManager` provider fallbacks. It does **not** invoke trade execution or the AI analysis pipeline. This is data-readiness instrumentation, not a 100-stock scanner UI.
- Per symbol, the JSON report records normalized, numeric, nonduplicated OHLCV row counts; first/last **completed** bar; latest expected `XIST` session; TRY provider currency metadata; and statuses such as `ready`, `fetch_error`, `no_data`, `invalid_data`, `stale_price`, `insufficient_history`, `calendar_unavailable` and `currency_unverified/mismatch`.
- No fabricated data: an unverified currency or missing calendar never counts as `ready`; exceptions are isolated by ticker. Historical bars for the still-open current day never count as complete, and the audit deliberately uses the preceding session as a conservative freshness bound. `with_valid_price_bars` is **not** the same as `ready` and neither means analyzed.
- Offline `tests/test_bist100_coverage.py` injects history and metadata (no network calls) for valid, stale, missing, invalid, delayed, unavailable and incomplete scans.
- **Manual smoke check** on a machine with Yahoo access, from repository root, starting with five tickers:
  ```bash
  python -m src.services.bist100_coverage --as-of 2026-11-15 --limit 5 --delay-seconds 2 --output bist100-coverage-smoke.json
  ```
- **Full 100-symbol audit** only after the smoke check, preserving rate-limit protection:
  ```bash
  python -m src.services.bist100_coverage --as-of 2026-11-15 --limit 100 --delay-seconds 2 --output bist100-coverage.json
  ```
- Review provider terms/usage and retry/429 policies before scheduled or commercial operation; Yahoo may have delayed/limited data. Never store or commit falsely complete outputs or claim `100/100` analyzed. The output JSON is local, not an ETRE/web interface; integration with the office is a separate pending step.

## Phase 5 — Web office read-only coverage JSON viewer (candidate, not deployed)

- `apps/dsa-web/src/pages/DataCenterPage.tsx` now mounts `Bist100CoveragePanel` regardless of whether the existing data-capability API succeeds. It never triggers a Yahoo request or analysis.
- The user can pick the `--output bist100-coverage.json` artifact in their browser. It is parsed **locally only** (not uploaded), limited to 2 MB, and displays 100 total, checked, ready, unverified/problematic, unchecked, status breakdown and a paginated per-symbol table.
- `apps/dsa-web/src/utils/bist100CoverageReport.ts` rejects false 100/100 summaries, duplicate/malformed `.IS` tickers, `XU100.IS` index entries, missing TRY/calendar/source metadata, invalid date/bar fields and inconsistent totals. `apps/dsa-web/src/utils/bist100CoverageReport.test.ts` contains offline defensive cases.
- This viewer is an **imported historical snapshot**, not a live data API or the actual AI-analysis completion counter. Local JSON may come from a trusted CLI run; authenticity and current index membership beyond format cannot be independently verified by a browser-only import. Report readiness must not be confused with successful trading analysis.
- To see results: execute the 5-symbol or 100-symbol audit in a network-capable environment, then open web office **Data Center** and choose the resulting JSON. No real Yahoo run was executed in this GitHub-only development session.
- Next integration gate: review CI and run the external Yahoo smoke test, then expose backend-produced validated reports over an authenticated, read-only API if appropriate. Keep production orders and ETRE/crypto/Hype unchanged.

## Phase 6 — Authenticated saved-report endpoint and auto-preview (candidate)

- `GET /api/v1/data/bist100/coverage` is **read-only** and never calls Yahoo or the AI-analysis pipeline. It uses the existing `/api/v1/data` route and requires **ADMIN_AUTH_ENABLED=true** plus a valid admin session cookie. If admin authentication is off, the endpoint is deliberately unavailable (404).
- The backend reads **only** the operator-configured absolute file path in `BIST100_COVERAGE_REPORT_PATH` (up to 2 MB), not a browser-supplied filename. Missing files return 404; invalid JSON or contradictory rows, counted symbols or metadata return 422. The validator checks each symbol against the source-dated BIST100 100-member snapshot. No stored file paths, credentials, or stock values are fabricated.
- In **Data Center**, the BIST100 coverage panel now tries this authenticated saved report once on page load. Users may click *Sunucu raporunu yenile* to read a newer server-side report, or select a local JSON file manually without upload. The page does not schedule scans or place orders. No data remains explicitly unavailable.
- Example operator setup (after creating a local writable directory with appropriate permissions):

  ```bash
  python -m src.services.bist100_coverage --as-of 2026-11-15 --limit 5 --delay-seconds 2 --output /absolute/path/bist100-coverage.json
  ```

  Configure `BIST100_COVERAGE_REPORT_PATH=/absolute/path/bist100-coverage.json` in the server runtime environment and `ADMIN_AUTH_ENABLED=true` in the application's existing admin-auth configuration. Restart the backend if needed. Open Data Center with an authenticated session to review **5 checked / 95 unchecked**, not a falsely complete 100-stock scan.
- Run the full audit only after the five-stock smoke succeeds, using `--limit 100` and appropriate provider limits; replace the same configured report file with the genuine output so the view refreshes. The report is a **historical snapshot as of its recorded date**; it is not live streaming or an AI completed-analysis counter. Avoid committing actual market data or server credentials.
- New offline tests in `tests/test_bist100_report_reader.py` verify file gating, authorized access, accurate partial counts and rejection of forged summaries. Integration requires a completed CI check; no 5/100-stock live Yahoo scan has been run from this GitHub-only environment.

## Phase 7 — Deterministic five-ticker Yahoo smoke and safe replacement

- The audit CLI now supports an **explicit active-member subset** to make the smoke result repeatable and deliberately exercise a mixture of liquid and newly admitted BIST100 symbols.
- First live trial on a machine/server with Yahoo access:

  ```bash
  python -m src.services.bist100_coverage --as-of 2026-11-15 --symbols THYAO.IS,ASELS.IS,AKBNK.IS,TUPRS.IS,AKFYE.IS --delay-seconds 2 --output /absolute/path/bist100-coverage.json
  ```

  This must report **5 checked / 95 remaining**, with truthful ready/missing/stale/error counters; do not confuse *checked* with *ready* or *AI analyzed*. If rate-limited or offline, keep the failed statuses.
- After observing 5-symbol provider results and confirming acceptable data usage/rate limits, run `--limit 100` (without `--symbols`) against the same saved output path.
- `_write_json_atomically` writes to a same-directory temporary file and replaces the destination only when the complete JSON is written; the authenticated read-only API therefore does not see a partly written audit during replacement. The older file remains intact on write failures.
- `tests/test_bist100_coverage.py` now includes offline checks for the exact 5-symbol CLI selection, invalid/duplicate symbols, mutually exclusive CLI filters and report replacement. **No actual live Yahoo smoke has been performed from this session**, because the environment cannot resolve Yahoo chart endpoint DNS. All tests still require CI verification.

## Phase 8 — Operator-confirmed live 100/100 coverage (2026-11-15)

- The BIST100 audit was run **on the operator's Windows PC**, on branch `feat/bist100-mvp`, after fixing an eager-import dependency failure by using the project's direct `yfinance` dependency in `_yahoo_daily_history` (commits `c2c4b2c7`, `47419995`). These are external operator-reported results, **not** a CI live-market test.
- Initial live smoke: `--symbols THYAO.IS,ASELS.IS,AKBNK.IS,TUPRS.IS,AKFYE.IS --as-of 2026-11-15` gave `checked=5`, `ready=5`, and `with_valid_price_bars=5`, all with TRY currency and 250 daily records per ticker, completed through 2026-11-13.
- Full live coverage: `--as-of 2026-11-15 --limit 100 --delay-seconds 2` produced `checked=100`, `ready=100`, `remaining=0`, `complete=true`, `with_valid_price_bars=100`, and `status_counts={\"ready\":100}`. No non-ready rows were shown in the operator's saved-report summary.
- **Scope boundary:** The audited JSON stores validation statuses and metadata, **not** the 100 full OHLCV history tables and **not** AI analysis outcomes. Do not imply the 100 price histories were imported into application storage or all stocks were screened/analyzed. Market data availability and index membership should be rechecked for later dates.
- **Next phase:** Bridge verified `.IS` histories to the existing application data-persistence and analysis pipeline; run offline integration regression tests and a bounded 5-symbol dry run before full analysis. Avoid uncontrolled cross-market provider fallback and unnecessary model or order execution.
- Product scope updated at the user's direction: BIST100 and equities stay in this repo; external office integration is not a development target; cryptocurrency work will be handled separately. Removing legacy crypto wiring requires its own reviewed changes, not an implicit mass deletion during the market-data feature.

## Phase 9 — Opt-in import into the existing analysis database (candidate)

- `src/services/bist100_import.py` reuses the validated BIST100 Yahoo fetcher and calendar/currency/ohlcv checks. **Unlike** the coverage JSON, it retains actual historical bars and can upsert them through the existing `src.storage.get_db().save_daily_data()` / `StockDaily` data model. `canonical_id` is the original .IS ticker, never a bare US or mainland code.
- The **default is dry run**: no storage module is imported or opened, and no database is changed. Run the same deterministic five-ticker smoke before any write:
  ```powershell
  .\.venv\Scripts\python.exe -m src.services.bist100_import --as-of 2026-11-15 --symbols THYAO.IS,ASELS.IS,AKBNK.IS,TUPRS.IS,AKFYE.IS --delay-seconds 2
  ```
- When the bot's normal Python application dependencies, especially SQLAlchemy, are installed and the intended `DATABASE_PATH` has been checked, the **operator may explicitly opt in** to a five-ticker DB write:
  ```powershell
  .\.venv\Scripts\python.exe -m src.services.bist100_import --as-of 2026-11-15 --symbols THYAO.IS,ASELS.IS,AKBNK.IS,TUPRS.IS,AKFYE.IS --delay-seconds 2 --write-db
  ```
  The default config's `DATABASE_PATH` is `./data/stock_analysis.db` relative to the repo root. An operator-provided `DATABASE_PATH` may point to a separate test database. Never put production DB files, credentials, or downloaded bars in Git.
- Only rows on or before the last conservatively completed XIST session can be stored. Every ticker requires valid numeric OHLCV, enough bars, current session and verified TRY metadata. The importer computes MA5/10/20 and percent-change from actual price history; other unavailable statistics stay NULL rather than fabricated. Read-back verifies expected dates after an UPSERT, including idempotent reruns.
- A successful import writes *historical prices*; it does not assert an AI analysis succeeded. `imported`, `ready_for_import` and `new_rows` are distinct counters. Individual storage failures are shown as `db_error`, never silently marked successful.
- Main analysis-pipeline compatibility, real DB smoke, AI report language and full-batch execution still require separate checks. Non-BIST provider imports are skipped when `get_market_for_stock()` is asked to identify a Turkish .IS symbol.
- Tests in `tests/test_bist100_import.py` run offline with an injected DB and cover dry run, fresh writes, idempotence, partial bars, stale/mismatched currency, per-stock DB errors and invalid symbols.

## Phase 10 — Read-only BIST100 technical screener (draft)

- `src/services/bist100_screener.py` reads the existing `stock_daily` SQLite table via `file:...?mode=ro` plus `PRAGMA query_only=ON`; it does **not** import or initialize the bot's database manager, run migrations, download prices, call LLMs, send notifications, or trade.
- For each 2026-Q4 member, it requires a validated past XIST last completed session, at least 60 actual daily bars, correct `Yahoo Finance` source and canonical `.IS` identity, and valid OHLCV. Missing rows, stale prices, unknown origin and invalid data are excluded from ranking with explicit statuses. SQLite has **no per-bar currency column**: source provenance is not independent proof of TRY, so the opt-in importer should be used to verify and populate the rows.
- It invokes the application's existing `StockTrendAnalyzer.analyze` to compute MA, MACD, RSI, trend and the existing 0–100 signal score. Non-finite/out-of-range indicators fail closed. Results are ordered by `score` descending with ticker as the stable tie-breaker. A score is a **technical ranking**, not an AI report or investment recommendation. MA5 bias above +5% sets `chase_risk=true` and `eligible_for_watchlist=false` even if the base analyzer emits a buy signal.
- Run *after* the separate five-symbol `bist100_import --write-db` smoke (and after installing the bot's full Python dependencies for StockTrendAnalyzer):
  ```powershell
  .\.venv\Scripts\python.exe -m src.services.bist100_screener --as-of 2026-11-15 --symbols THYAO.IS,ASELS.IS,AKBNK.IS,TUPRS.IS,AKFYE.IS --db-path ".\data\stock_analysis.db" --output ".\bist100-technical-5.json"
  ```
  If the existing database uses a different path, use the same configured `DATABASE_PATH` as the importer. **The 100/100 coverage JSON is not a database and cannot be screened**. A stock with no imported rows returns `not_imported`, not an invented score.
- After a successful full, explicit 100-member history import, omit `--symbols` for 100-member read-only screening. This is *not* a deployment-ready consumer report UI or end-to-end AI analysis.
- `tests/test_bist100_screener.py`: offline coverage for ranking, stable ties, completed-session checks, missing/stale or non-Yahoo data, chase-risk exclusion, invalid rows, analyzer failures, existing analyzer smoke, and SQLite read-only enforcement. Pending CI until run reports its result.

## Phase 11 — Admin-gated BIST100 technical-ranking viewer (draft)

- The Data Center page now includes a separate **BIST100 · Teknik sıralama** panel. It displays only an existing technical-ranking JSON generated by `src.services.bist100_screener`; it does **not** run analysis, fetch market data, call AI, migrate SQLite, or place trades. This is distinct from the existing Yahoo coverage panel: `100/100` downloaded price coverage **does not** prove 100 completed technical analyses.
- An authenticated-admin **read-only** API `GET /api/v1/data/bist100/technical-ranking` reads only the operator-configured absolute file path in `BIST100_TECHNICAL_REPORT_PATH`. With admin authentication disabled, the endpoint returns 404; without a valid admin cookie, 401. Neither query parameters nor URL paths select filesystem files. The file must be at most 2 MB and pass dated BIST100 membership, score/rank, session freshness, completeness counter and chase-risk consistency validation. Missing report returns 404 and invalid returns 422, never fabricated zero counts.
- The React panel can alternatively open a **local JSON file** on the viewer's device; local files are parsed in the browser, not uploaded, and display the filename and report date. It shows processed/unprocessed counts, status breakdown, a paginated technical score table, and a separate MA5 chase-risk warning. Local validation checks shape, dates, rank ordering, and counts but cannot independently prove that the user-selected file was generated by the Python screener.
- With an explicitly populated local SQLite database, generate a report on the host machine, for example:
  ```powershell
  .\.venv\Scripts\python.exe -m src.services.bist100_screener --as-of 2026-11-15 --symbols THYAO.IS,ASELS.IS,AKBNK.IS,TUPRS.IS,AKFYE.IS --db-path ".\data\stock_analysis.db" --output ".\bist100-technical-5.json"
  ```
  The generated JSON can be selected directly in the Data Center browser, even when the admin endpoint is not configured. To use server viewing, set `BIST100_TECHNICAL_REPORT_PATH` on the **backend host** to the absolute saved JSON path and use a valid administrator login; do not enable unauthenticated access.
- Both report-producing and viewer steps remain **manual and opt-in**. No current report is auto-created from the earlier 100/100 coverage audit. CI tests verify only mock/fixture cases until real five-stock SQLite reading and 100-stock execution are completed. Keep Draft PR #8 unmerged pending review.

## Phase 12 — Real Yahoo → isolated SQLite → technical ranking (operator run)

The repo now includes `scripts/bist100-live-validation.ps1`, an opt-in Windows PowerShell validation runner.

**Safety and truth boundaries:** The runner requires the checked-out `feat/bist100-mvp` branch and an installed `.venv\Scripts\python.exe`. It uses `src.services.bist100_import --write-db` **only after assigning a newly created isolated SQLite file to the process-local `DATABASE_PATH`**. The original `DATABASE_PATH` is restored afterward; no app/production database is opened, deleted or overwritten. The run folder is unique under `%LOCALAPPDATA%\EBBOTCYBER\BIST100-Validation`. Reports, stderr diagnostics and the isolated database remain there. No order placement, LLM calls or push to a remote server.

The script checks the selected 2026-Q4 membership and strictly requires fresh, TRY-denominated Yahoo rows for every selected symbol. It runs a five-stock `THYAO.IS,ASELS.IS,AKBNK.IS,TUPRS.IS,AKFYE.IS` import and the **existing** technical analyzer, stops on any unavailable/import-error/unanalyzed stock, and saves `import-5.json` and `technical-5.json`. Run after checking out the PR #8 working tree and installing Python dependencies:

```powershell
.\scripts\bist100-live-validation.ps1 -AsOf 2026-11-15
```

Only after the five-stock gate passes should the operator explicitly request the complete index. The same staging DB is reused inside that one run, and both 100-stock import and ranking **must** pass 100/100 or the runner errors with paths to inspect:

```powershell
.\scripts\bist100-live-validation.ps1 -AsOf 2026-11-15 -Full100
```

The `-AsOf` date is required and must lie within the verified 2026-Q4 constituent snapshot. Tests in `tests/test_bist100_live_validation_script.py` are static/offline safeguards; they do **not** imply real Yahoo requests completed. The script itself needs to be run on an operator-controlled Windows machine with external data-provider access. When the run passes, open the generated `technical-5.json` or `technical-100.json` locally in the Data Center technical-ranking panel, or configure the backend's `BIST100_TECHNICAL_REPORT_PATH` to the absolute file path for administrator-only viewing. Rerun with a new date/snapshot for later periods.

CI passing **is not** proof of real historical provider availability, complete index analysis, or model profitability; keep every report's sample size and as-of date visible. This script does not modify the main app database, and results from the isolated database should not be treated as a production migration verification.

## Phase 13 — Saved technical report session-freshness protection (draft)

- **Server-side validation:** The authenticated read-only technical ranking API now rejects a JSON report unless `last_completed_session` exactly matches the *verified previous XIST exchange session* for the report's `as_of` date. A report with internally matching but stale stock-bar dates no longer passes just because its dates agree with each other. If the exchange calendar cannot be verified, it fails closed with HTTP 422; no guessed trading dates or fabricated current price are returned. Weekend and holiday dates are resolved from the exchange calendar.
- **Browser-side limitation:** A locally selected JSON file is never uploaded and gets structural/ranking/counter validation, but its source authenticity and official exchange session **cannot** be independently verified by the browser. The panel explicitly warns of that difference. The `watchlist_eligible` count only means that the MA5 chase-distance filter passed, **not** a buy recommendation or a risk-approved portfolio selection.
- These changes do not fetch prices, run AI, send orders, overwrite the SQLite database or automatically publish GitHub Actions reports. Previous 100/100 BIST100 historical rankings remain **dated snapshots**, not live market prices.

## Phase 14 — Read-only ranking exploration in the Data Center

The existing historical technical report viewer now offers four **client-side, presentation-only** controls: stock-code search, an MA5 *chase-distance warning* filter, a minimum saved technical score (0/60/70/80/90), and a view order (original rank, alphabetic ticker, descending RSI). The table includes the already-recorded MACD histogram. The default remains the validator-confirmed, original technical rank order.

- **No new ranking calculations**: Sorting by RSI or symbol never changes the original `rank` or `score`, recomputes indicators, requests another data provider, runs an LLM, or sends an order.
- **No misrepresented coverage**: Summary counters continue to represent the *entire verified report*, while a separate line explicitly labels the number of currently visible rows after filters. An empty result is labeled as a filter mismatch, not a scan/data failure.
- **Not a buy list**: `ma5-clear` means the recorded `chase_risk` warning is false; it does not imply an approved investment, low overall risk or a profit prediction.
- **Historical provenance**: Existing source/session warnings and the server's XIST calendar validation remain intact. Local JSON is parsed in the browser, but its original author and official completed session cannot be independently verified there.

`apps/dsa-web/src/utils/bist100RankingView.test.ts` exercises filtering, sorting, equal-score source ranks, immutability, no-match handling and invalid thresholds. The PR frontend CI runs these tests and the existing report-parser tests before lint/build. The 100/100 Yahoo Finance historical backfill proof from PR #8 does **not** mean this new UI has been deployed or connected to a persistent production database.

## Saved OHLCV coverage XIST session hardening (draft PR #18)

The server-side **saved price-coverage** reader now follows the same independent
exchange-calendar verification as the previously hardened technical ranking:

- The report's claimed `expected_last_completed_session` must match the
  independently computed previous completed **XIST** session for the report
  `as_of` date. Internally matching but stale `ready` rows are rejected with
  HTTP 422 rather than shown as current.
- Snapshot identity is checked against the 2026-Q4 dated 100-stock roster:
  the `constituent_snapshot_as_of` and
  `constituent_snapshot_effective_to` fields must match the loaded universe.
- A report which genuinely cannot verify its exchange calendar can still show
  diagnostic `calendar_unavailable` results with **zero** `ready` symbols;
  it is not silently upgraded to verified price coverage.
- The local-browser JSON viewer verifies **internal** session/row consistency
  and prominently warns that it cannot independently attest the calendar or
  origin of user-selected files. The backend verifies XIST for saved reports.
- Independent offline regression tests cover fabricated previous sessions,
  unavailable server calendar, false roster metadata, a 422 authenticated
  response, and preserved unverified-only diagnostic reports. CI now runs the
  coverage parser's Vitest suite and backend coverage reader test in the
  dedicated pre-merge gate.

All data remains historical. This change performs no Yahoo queries, stock
analysis, orders, SQLite writes, API uploads or production publication.
