# EBBOT-CYBER seven-market consolidated candidate — release decision record

**Prepared:** 2026-11-15
**Decision:** HOLD (draft code / CI verification only). **No merge or production deployment authorized.**

## Exact stable candidate

The consolidation branch `release/seven-market-consolidated-candidate`
forks from **draft PR #21** `feat/six-market-saved-smoke-api`,
which includes the reviewed BIST100, source routing, SQLite safety,
exchange-session gating, historical ranking and seven-market Data Center
work from earlier stacked drafts.

**Do NOT import PR #22's one-off artifact-download E2E workflow into the
long-lived release branch:** the original Yahoo JSON artifact has finite
retention and default CI must remain deterministic. PR #22's historical
six-real-example end-to-end proof is evidence, *not* a dependency or a
perpetual data feed.

| Scope | Proven so far | Not proven / not authorized |
| --- | --- | --- |
| Turkish BIST100 | One historical 100/100 Yahoo OHLCV import, 100 ranked technical results; last completed XIST session and original saved-report-to-React integration were tested in **disposable GitHub runners** | Automatic daily update, real-time price guarantees, official 2027-Q1 members, production report publication |
| China | Historical 600519.SS single-example Yahoo + analyzer verification | All A-share issuers, real-time primary-source routing |
| Hong Kong | Historical 0700.HK single-example verification | Full HKEX equity universe |
| USA | Historical AAPL single-example verification | Full NYSE/Nasdaq equity universe |
| Japan | Historical 7203.T single-example verification | Full JPX equity universe |
| South Korea | Historical 005930.KS single-example verification | Full KRX equity universe |
| Taiwan | Historical 2330.TW single-example verification | Full TWSE/TPEx coverage; TPEx 403 must remain labeled access-unverified |
| Authenticated Data Center | Read-only BIST technical report, BIST OHLCV coverage, and historical six-market admin report; dated historical status, per-market counts, locally selected JSON fallback and no-evidence default | Production uptime, all-market coverage, investing advice, online approval/publishing |
| Database and trade boundaries | SQLite migration guard tests, market isolation and no-write report-reader tests pass on sandbox repositories | Safety of a specific **live** SQLite database without backup/recovery rehearsal; placement of real orders |

## Sources for historical evidence

- [BIST100 100/100 historical Yahoo run](https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/43723300907)
- [Six-market one-symbol-per-exchange live Yahoo smoke](https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/43725877201)
- [Historical 100-stock JSON → BIST API → React DOM proof](https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/43732003049)
- [Historical BIST JSON → SHA-gated sandbox publish → saved report reader](https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/43736198210)
- [Historical real six-stock JSON → six exchange calendars → authenticated API → React DOM proof](https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/43753246364)
- [PR #21 deterministic report-reader backend + frontend checks](https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/43751967129)

Historical artifacts used by these proofs have finite retention; acceptance
of the present candidate must rely on its **new full source-code CI**, not
the future availability of those artifact files.

## CI required on the exact consolidation commit

1. Frontend: `npm ci`, TypeScript, the BIST saved report parsers, one-example
   six-market parser, seven-market admin panel DOM tests, ESLint, production build.
2. Backend: the full offline `pytest -q -m 'not network'` suite; the excluded
   live network tests are **not** successes. Report failures and actual counts.
3. Focused deterministic premerge gate:
   `tests/test_market_sqlite_pr2_integration.py`,
   `tests/test_bist100_six_market_integration.py`, 2026-Q4 and 2027
   missing/quarterly roster tests, BIST XIST session and technical
   ranking readers, report publisher path/SHA/atomic no-overwrite safety,
   six-market SHA/session/auth reader, and
   `tests/test_seven_market_release_contract.py`.
4. The new cross-API test uses *synthetic partial BIST and six-example
   fixtures* and explicitly verifies that a missing or rejected report in
   one market group **does not forge a success or hide the other group's
   valid report**. It tests both endpoints' 401/404/422 handling,
   path query isolation, `no-store` and byte-for-byte **no writes**.
   It does not substitute synthetic bars for the already completed
   historical real-source verification.

## Manual production and merge gates (not yet completed)

- [ ] Independent review of the **full** `main...release` diff
  (source/calendar, stock market routing, auth, API, storage, docs, Actions).
  Re-compare against `main` immediately before merging; don't merge the
  overlapping stacked drafts independently.
- [ ] Confirm production OS/filesystem permissions, accepted report paths,
  the report SHA-256 independently sourced from approved actual JSON,
  market-data rights and every report's `as_of`/last session.
- [ ] Prove the current production SQLite schema and version against an
  **offline copy**, with a verified backup and restore rehearsal.
  CI on temporary SQLite is not the same as validating an existing DB.
- [ ] Obtain and independently source-review real 2027-Q1 BIST100 members
  before attempting 2027 scans; 2026-Q4 must **never** silently roll over.
- [ ] Review all external market data licensing and provider rate limits;
  test additional symbols in CN/HK/US/JP/KR/TW before any claim of
  all-market readiness.
- [ ] Review authentication, session secret deployment, report path integrity
  and endpoint monitoring. A SHA-256 set by the operator does not prove
  the upstream Yahoo data's authenticity.
- [ ] Document retention, backup/rollback of report files, service restart,
  and the response for missing, invalid or old reports.
- [ ] Receive **explicit user approval** for the exact merge commit and,
  separately, any production configuration/deployment. A green CI cannot
  substitute for these approvals.

**Current boundary:** This draft itself makes no production modification,
does not run new Yahoo calls, paid AI, broker operations, local stock order
execution, server uploads or live SQLite migrations.
