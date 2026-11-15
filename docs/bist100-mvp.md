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

- `src/services/bist100_coverage.py` audits the dated **100**-stock snapshot through the existing `YfinanceFetcher` daily-data path **only**, without `DataFetcherManager` provider fallbacks. It does **not** invoke trade execution or the AI analysis pipeline. This is data-readiness instrumentation, not a 100-stock scanner UI.
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
