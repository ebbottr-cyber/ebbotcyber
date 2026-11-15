# EBBOT-CYBER: unified seven-market read-only release candidate

**Status: HOLD — draft-only source code, no approval to merge, deploy, trade,
configure a live server, publish a paid report, or change any production DB.**

**Consolidation decision (2026-11-15):** PR #23 and PR #24 diverged after
their common **PR #21** base. PR #24 contains additional future-report
validation and its own 401/404/422 / zero-write regression suite.
PR #23 adds a separate dual-API acceptance suite, including spoofed
historical SIX-market sessions and tampered BIST sessions. **Both suites
are included** in this single candidate; overlapping branches #23 and #24
must NOT be independently merged into main.

## Historical evidence (no new market fetch in this candidate)

| Scope | What was independently checked | What was NOT established |
| --- | --- | --- |
| Turkey BIST100 | One actual historical 100-stock Yahoo daily-bar import / technical ranking; one saved 100-stock report through XIST session validation and React panel | Live price stream, scheduled data sync, full production publication, investment advice |
| China | Yahoo 600519.SS historical example | All mainland listed equities |
| Hong Kong | Yahoo 0700.HK historical example | All HKEX securities |
| USA | Yahoo AAPL historical example | All US stocks and broker/data-provider routing |
| Japan | Yahoo 7203.T historical example | All JPX stocks |
| South Korea | Yahoo 005930.KS historical example | All KRX stocks |
| Taiwan | Yahoo 2330.TW historical example | All TWSE/TPEx symbols; TPEx HTTP 403 is access *unverified* |

Actual 6/6 example-stock JSON was checked against its externally
recorded SHA-256, independently computed previous completed exchange
sessions, authorized admin-only saved report API and the React Data
Center component on the temporary PR #22 test runner:
https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/43753246364

The separate actual BIST100 100-stock report-to-panel and read-only
publication checks also ran on disposable GitHub Actions runners:
https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/43732003049
https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/43736198210

**Neither short-retention original artifact nor time-limited E2E job from
PR #15 or PR #22 is committed to this long-lived release candidate.**
The historic proof does not mean these files are installed on a
production server.

## Code-level assurance brought together

- BIST100 source-reviewed **dated** 2026-Q4 candidate member list
  expires 2026-12-31. Until the *actual* 2027-Q1 roster is verified
  and checked in, future-quarter membership queries **fail closed**;
  no guessed tickers, stale 100-stock rollovers, or extra benchmark.
- Read-only BIST100 technical report / saved OHLCV coverage routes are
  protected by admin sessions and independent last-completed XIST dates.
  The guarded BIST100 file publisher requires a digest and explicit
  operator action and prevents concurrent first-write overwrite.
- The six foreign markets have exactly **one historical sample ticker
  per market**; saved report reader requires an existing absolute
  non-symlinked JSON file and separately configured operator-approved
  SHA-256, the right original six market identities, honest analyzed
  counters and independently checked historical exchange sessions.
  Future as-of dates (Europe/Istanbul) and same-day/future last price
  bars are rejected, including failed diagnostic rows.
- Data Center displays a seven-market **historical evidence** table,
  not live health indicators; no approved report means *no evidence*.
  The browser can optionally use a local JSON, but the selected file
  is not independently source-verified and never uploaded.
- Combined GitHub CI exercises both independent security suites:
  `tests/test_seven_market_readonly_acceptance.py` from PR #24 and
  `tests/test_seven_market_release_contract.py` from PR #23. Both
  verify a single admin cookie, 401/404/422 rejection paths, query
  parameter path/scan isolation, report independence and absence of
  server file mutations. The second additionally proves that a
  forged, internally consistent *old* six-market session or
  manipulated BIST session cannot be accepted after all checks.
- Existing SQLite P0 migration safeguards and routing isolation tests
  remain part of the focused offline acceptance gate. This gate never
  runs Yahoo, invokes an LLM, places orders, deploys a server, or
  uses a production database.

## Required result of this exact draft head

1. Frontend TypeScript, focused Vitest (BIST100/one-symbol per market),
   ESLint and production build all successful.
2. Full offline Python suite successful, with exact passed/failed counts
   and optional live network tests declared **deselected**.
3. Focused release-premerge CI job successful on *both* additional
   contract suites plus earlier migration, session, quarterly roster,
   read-only publisher and calendar tests.
4. Compare the full PR diff against current `main` immediately before
   any review: stacked changes cover many pre-existing files, and two
   successful focused tests do not prove production deployment safety.
5. Do not merge PR #23, PR #24 and this PR separately. This unified
   branch is the single candidate for **review only**, without
   constituting permission to merge.

## Human hold points before a production decision

- [ ] Written acceptance of the exact proposed merge commit.
- [ ] Confirm data licensing and right to use each exchange/Yahoo source.
- [ ] Independently verify 2027-Q1 official BIST100 roster before a 2027 scan.
- [ ] Review current main diff, market routing, account authentication
      and release deployment environment.
- [ ] Identify and back up the **actual** existing production SQLite,
      validate its current schema, rehearse restore on an isolated copy.
- [ ] Approve each server report file (path, SHA-256, session, age,
      permissions) and have a rollback plan for a new report file.
- [ ] Approve separately any merge, deployment, provider downloads,
      paid AI use or live broker interaction.

No user device action is required to review this draft or run its
ordinary GitHub tests. None of the hold points above has been
implicitly authorized by a passing CI.
