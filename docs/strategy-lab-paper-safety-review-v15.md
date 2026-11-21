# EBBot V15 — pre-merge safety review of prospective paper operations

V15 is an *unmerged safety follow-up* to the [combined V14 draft](https://github.com/ebbottr-cyber/ebbotcyber/pull/54). It neither starts a PC/VPS observer nor creates a new broker/paper-trading execution pipeline.

## Verified security boundaries in code

- `POST /api/v1/strategy-lab/paper/inspect` **refuses when admin authentication is disabled**. When enabled, `/api/v1/*` is protected by the existing signed-cookie `AuthMiddleware`; the paper inspection route is not exempt.
- Inspection accepts at most **512 KiB**, cannot read arbitrary server-side paths, never stores an uploaded paper journal, and returns only sanitized historical paper summary and last 40 entries. Client upload requires an explicit local file selection; there is no auto-upload.
- A user-owned JSONL journal is SHA-256 chained and checked for sequence/date/source/rules before appending. Note: this is *tamper detection*, not cryptographic proof of independent data provider accuracy; administrators with file write access can recompute hashes.
- The paper observer starts from virtual cash at 1.0, uses the existing next-market-close virtual fill and user-specified per-side fee/slippage, and contains no broker/order/wallet write path.
- The operator wrapper defaults to **preview only**. It creates no schedule and can optionally send only a generic error notification (if explicitly enabled).
- No daily-analysis GitHub Action has been re-enabled and no environment secrets have been embedded.

## Issues discovered and fixed

1. **Delayed first observation incorrectly labeled prospective**: the shared `get_effective_trading_date` API intentionally returns the last completed date when run over a weekend, market holiday or before market close. Previous V9 CLI could create a *new* prospective paper journal for that historical close when `--commit` was passed. V15 explicitly refuses a committed record unless `as_of` equals the current local Shanghai date, as well as preserving the existing calendar/close/data-quality guards. Ordinary `PREVIEW_ONLY` still permits viewing the last completed session and never writes the journal. Tests freeze a legitimate Friday close and confirm weekend and next-week pre-close commits are blocked.
2. **Offline status incorrectly rejected by V10 wrapper**: `run_etf_paper_daily_v10.execute` previously raised an exception for **every** `--status` invocation, even with different journal and health file paths. V15 allows the harmless offline journal status read and labels its local health result `STATUS_ONLY`. It continues refusing `--status --commit` and status files that point to the journal itself. Tests confirm no trade, no network, no notification and no journal write.

## Remaining release blockers

- Passing synthetic CI is NOT evidence of real prospective daily observations or financial alpha.
- The preceding V14 candidate's full repo Python regression must pass at its exact HEAD. Focused V15 tests must also pass; the combined full suite should be rerun on the hardening commit before promotion.
- Independent human review and deployment smoke with admin session and a manually selected real journal file are not yet complete.
- Persistent PC/VPS operation, provider availability at actual China exchange closes, journal backups, optional notification delivery and explicit scheduler opt-in remain unconfigured.

The original V14, V13, V12 and all older Strategy Lab PRs remain draft, unmerged. Do **not** merge V15, V14 or any parent automatically. No real trading, auto-analysis, strategy promotion, or unattended paper recording is authorized by this review.
