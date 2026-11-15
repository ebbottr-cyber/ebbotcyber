# EBBOT-CYBER seven-market read-only release acceptance

**Status: Draft source-only candidate. Not approved to merge or deploy.**

## Consolidated code

This branch descends from **PR #21, not PR #22**. It includes the BIST100
historical report and secure publication workflow, XIST validation, 2027
quarterly roster fail-closed handling, six single-symbol international
Yahoo fallback samples, SHA-256-pinned admin-only saved report endpoint,
and React Data Center read-only historical evidence table. It retains
the previous SQLite safety and seven-market routing protections.

The separate **PR #22** demonstrated a real archived six-sample Yahoo
historical report through six exchange calendars, the authorized
read-only API and React DOM tests:
https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/43753246364

PR #22 contains a time-limited GitHub artifact integration CI job and
must **not** be merged into permanent PR verification. This PR builds
on PR #21 and deliberately does not include the expiring archive job
or the original historical market-data file.

## New safety in this candidate

- Reject a six-market historical report whose as-of date is in the
  future according to Europe/Istanbul local date (producer convention).
- Reject an invalid report-date or future bar even on **failed** sample
  rows. A failed symbol may be displayed for diagnostics, but it cannot
  claim impossible dates.
- Offline combined API acceptance verifies that one admin session
  gates both BIST and six-market saved reports, their respective 200
  responses and no-store headers, 401 without valid session, 404 when
  auth is disabled, and that extraneous query parameters do not choose
  a server file or launch a provider probe.
- Missing BIST approval leaves the independently approved six-market
  example report available. An invalid six-market checksum produces
  422 without compromising the BIST report.
- The deterministic tests use temporary, explicitly *synthetic*
  records and verify no GET request changes or creates output files.
  These are stable contract tests, separate from PR #22's actual
  original historical report proof.

## Manual hold points

1. Exact-head frontend typecheck, Vitest, lint and build must pass.
   Full offline Python and focused release critical security suite
   must finish successfully. Live provider checks excluded from
   routine PR CI are *skipped*, not passing.
2. Compare the full candidate diff with current main. The past
   stacked PRs overlap; do not merge each draft independently.
3. The real 2027-Q1 BIST100 membership is **not present**. 2027
   analyses must still fail closed until source-reviewed constituents
   are supplied.
4. The six foreign markets still have **one verified historical
   example stock each**. The combined panel does not show entire
   foreign exchange coverage or real-time provider health.
5. Production server path configuration, report publication, backup
   and SQLite migration need separately reviewed operator approval.
   Do not spend on LLMs, deploy services, or place orders from CI.
6. Human authorization is mandatory before a main-branch merge.

No main branch, production server, live database, portfolio state,
trading credentials, billing or orders are changed by this draft.
