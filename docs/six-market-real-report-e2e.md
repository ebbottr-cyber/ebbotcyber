# One-time real six-market historical report → admin API → React Data Center

**Source:** Archived real Yahoo historical technical provider-fallback smoke
generated in a separate successful run and stored as GitHub Actions artifact.
This is a source-backed **6/6 *example stocks*** report, not 6 complete equity
universes, not live prices, not paid AI output, not broker orders.

## Source record

- Historical source run: https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/43725877201
- GitHub artifact: `six-market-yahoo-smoke-43725877201` (artifact ID `14167015110`)
- Exact JSON filename inside ZIP: `six-market-yahoo-2026-11-15.json`
- Exact historical JSON SHA-256:
  `e2a4f357add80d7dc11ec305aab7a2fa0707f583763db36258c89cddd84d6bd2`
- Report date: **2026-11-15**, historical last completed session **2026-11-13**.
  Each of six example probes was marked `analyzed`:
  CN `600519.SS`, HK `0700.HK`, US `AAPL`, JP `7203.T`,
  KR `005930.KS`, TW `2330.TW`.
- Observed historical sample technical scores in original JSON (not
  recommendations): CN 57, HK 39, US 75, JP 72. Each actual report
  sample had 60+ daily bars. These values must not be shown as new/live.

## Test design

The dedicated `six-market-real-saved-report-e2e` GitHub Actions job is
limited to draft branch `integration/six-market-real-report-readback`.
It downloads the original artifact using an Actions read-only token.
It **fails** if the artifact is missing or its exact SHA-256 differs:
never substitutes generated OHLCV or simulated markets.

1. Compare the *original file's* SHA-256 with the pinned external fingerprint
   (not a checksum calculated and then accepted without reference).
2. Using `integration-tests/six_market_real_artifact_e2e.py`, compare the
   archived six market identifiers, tickers, dates, bar counts and statuses
   with `src.services.six_market_live_smoke.PROBES`. Independently obtain
   previous real exchange sessions from `get_trading_dates`; verify XIST
   is *not* silently substituted for international calendars. Exercise the
   operator-pinned server reader and authenticated GET route end-to-end.
   Repeat with a fabricated internally consistent *stale* session and
   confirm it fails closed.
3. Using `apps/dsa-web/integration-tests/sixMarketRealSmoke.e2e.test.tsx`,
   parse the **same exact JSON**, mount the actual Data Center React
   component and verify the six different sample tickers and historical
   status while BIST100 correctly shows **no** saved report. Mock the
   already-proven admin HTTP boundary, not source data or seven rows.
4. Repeat without a configured six-market server report: the component
   must show **0/7** evidence and must not promote the six historical
   results to live/exchange-wide coverage.

## Release and retention

The previous GitHub artifact is retained for only a limited time (7-day
retention in the original workflow). This is a **one-off draft integration
proof**, not a test to merge into default `main` or long-lived CI. If it
expires, the job must report unavailable rather than silently succeed
against synthetic records.

The ordinary deterministic `tests/test_six_market_smoke_report_reader.py`
remains suitable for long-lived CI and already verifies admin 401/404/422,
hash pinning, calendar/session correctness, symbol/currency integrity
and symlink/path guards. This additional one-off gate tests the **actual
historical six-market artifact through those same contracts**.

No actual report is installed in production; no server config, SQLite,
market-data feed, AI billing, deployment, real order or main branch is
changed. Any future production upload requires separately authorized
operator review and correct licensing.
