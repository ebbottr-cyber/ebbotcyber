# EBBOT-CYBER seven-market pre-merge review — 2026-11-15

**Status: draft candidate; not authorization to merge, deploy, trade or modify production databases.**

## What the candidate actually proves

| Scope | Verified evidence | Boundary |
| --- | --- | --- |
| BIST100 2026-Q4 candidate constituent list | 100 distinct .IS stock tickers, excludes XU100.IS index | Dated 2026-10-01–2026-12-31 snapshot; obtain a refreshed, source-reviewed list after expiry |
| BIST100 Yahoo Finance OHLCV | Historical 100/100, 24,996 inserted rows to disposable SQLite (PR #8 green runner) | **Not** scheduled data sync, today's live quotes or permission to redistribute market data |
| BIST100 technical report | 100/100 historical technical ranks; SHA-256-verified 2026-11-15 JSON, last completed XIST session 2026-11-13 | One dated technical snapshot; not AI recommendation or execution |
| Data Center browser UI | PR #14 parser, filters, RSI/MACD, responsive render; PR #15 real 100-stock JSON → server XIST validator → TypeScript/React E2E (10 tests) | No production deployment or automatic report import |
| BIST100 report publication | PR #16 sandbox read-only preview → explicit checksum-gated publication → readback of 100/100 saved report | Temporary GitHub runner only; no production path set or backup altered |
| Other six markets CN/HK/US/JP/KR/TW | PR #9/#10/#11 real Yahoo smoke with **one representative symbol per market** and real currency checks | **Not** full-market tickers, continuously refreshed coverage or integrated six-market portfolio dashboard |
| SQLite legacy migration safety | PR #2 safeguards integrated via PR #11, deterministic regression tests, no production DB writes | Actual production backup/restore and schema-specific migration review remain required |
| TPEx Taiwan institutional flow | PR #13 separates HTTP 403/rate-limit from authenticated HTTP 200 schema drift | HTTP 403 is **unverified connectivity**, not a successful production TPEx integration |

Historical test references:
- [PR #8: BIST100 real import and 100-rank](https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/43723300907)
- [PR #11: SQLite safety and six-market sample Yahoo](https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/43725877201)
- [PR #15: real report-to-panel E2E](https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/43732003049)
- [PR #16: real report preview, publication and readback on temporary runner](https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/43736198210)

## Branch and merge safety

- The long-lived, stacked candidate is **release/seven-market-premerge-safety** based on the already-green PR #16 branch, which itself carries PR #14 → #13 → #12 → #11 → #10 → #8. The earlier PR #2 SQLite and PR #9 six-market files were selectively integrated and tested in later branches. The separate PR #15 contains a **time-limited GitHub artifact** integration workflow; do **not** merge an expiring artifact dependency into long-lived default CI.
- Do **not** merge independent stacked feature PRs one after another without comparing their commits and file overlaps; this can duplicate changes or unexpectedly overwrite newer BIST code. Prefer one explicitly reviewed consolidated candidate after the final checks and owner approval.
- On 2026-11-15, PR #16 was 112 commits ahead of main, zero behind, and touched 78 files. Those figures are a review scope, **not** proof of main branch release fitness; repeat comparison immediately before any approved merge.
- Source and target must be explicitly approved. Release publishing always defaults to read-only preview, cannot override the operator's configured `BIST100_TECHNICAL_REPORT_PATH`, rejects symlink destination and **any symlinked parent ancestor**, and requires a separately approved SHA-256 and explicit `--publish`. Replacing an existing file requires `--replace-existing`; concurrent first-publication cannot overwrite.
- Never automatically add production config, paid LLM credentials, trading keys, private data, deployed services, scheduled execution, or live order routing to this merge.

## Acceptance gate before considering a merge

1. **GitHub CI on the exact release candidate head:** frontend typecheck, ranking Vitest, lint and build; full Python offline suite; targeted release preflight tests (SQLite reset, seven-market classification, XIST session, operator-only publishing, symlink/race guards). All must complete successfully, with live network tests disclosed as excluded rather than misreported as passing.
2. **Review the diff** against the current `main`, especially `src/storage.py`, `src/market_context.py`, `data_provider/base.py`, `data_provider/yfinance_fetcher.py`, `.github/workflows/pr1-verify.yml`, `requirements.txt`, data-center files and security/auth boundaries.
3. **Database safety:** identify the exact target SQLite version/schema; take a separately verified backup and restore rehearsal. A passing disposable-runner DB test is not permission to migrate an existing user's DB.
4. **Data provenance and licensing:** confirm Yahoo/BIST/TPEx usage terms, symbol/currency semantics, market-calendar holiday/half-day rules and reporting cadence. Do not imply complete CN/HK/US/JP/KR/TW market coverage from six sample symbols.
5. **Operator acceptance:** specify the report publication location, file permissions, backup/rollback plan, admin authorization, data age messaging and failure display. Any actual report copying and server configuration is a separate explicit action.
6. **Human approval:** only then decide whether to merge the consolidated branch to `main`. A green CI check alone does **not** grant permission.

## Deployment status

- Current changes are source-only in draft PRs; no live trade, paid AI call, production SQLite modification or deployment has been authorized.
- Historic 2026-11-15 data must remain explicitly dated on every UI surface.
- The new fast premerge test job runs on an isolated GitHub runner and performs only offline tests. It never calls price sources or places orders.
