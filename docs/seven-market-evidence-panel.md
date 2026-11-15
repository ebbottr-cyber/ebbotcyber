# Data Center: seven-market historical evidence panel (Draft PR #20)

## Purpose, not a live-exchange claim

The Data Center now shows **seven rows all the time**: BIST100/Türkiye
(`tr`) and China (`cn`), Hong Kong (`hk`), US (`us`), Japan
(`jp`), South Korea (`kr`), and Taiwan (`tw`).

**There is no automatic live data polling, no scheduled scan, no AI report
creation, no database write, and no trading order.** When no saved data
is available, every row says **Kaydedilmiş kanıt yok** and counts remain
zero rather than implying green market status.

The panel reads two fundamentally different pieces of historical evidence:

1. **BIST100:** the already existing, authenticated, read-only saved
   technical report API (`GET /api/v1/data/bist100/technical-ranking`).
   The backend verifies the dated **100-member constituent roster**,
   XIST session, rank/order/counters, technical indicators and risk flags.
   The panel shows the actual **checked** and **analyzed** counts from
   that report, the report `as_of` date, and previous completed session.
   On 2026-11-15, GitHub's isolated-runner test proved 100/100 on the
   specific historical report; this does not automatically publish that
   artifact to a production server. A missing configured report is
   explicitly **no evidence** in the UI.
2. **Six international markets:** an operator may manually select the
   JSON output from `src.services.six_market_live_smoke` in the browser.
   This is only **one example equity per market**:
   CN 600519.SS, HK 0700.HK, US AAPL, JP 7203.T,
   KR 005930.KS, TW 2330.TW. The strict browser parser confirms
   `scope=six_market_yahoo_fallback_one_symbol_each`, six unique
   market/example/currency identities, the per-row status, reported
   sample dates and OHLCV scores, positive-case >=60 bars, matching
   claimed previous-session and last-bar dates, and matching aggregate
   status counters. If one market fails, its failure stays visible.
   **It does not verify** actual Yahoo origin, true exchange-calendar
   freshness, or the rest of each foreign market's stock universe.
   Imported JSON **never leaves the browser**.

The panel distinguishes historical samples from complete stock coverage.
The display status **Tarihsel raporda analiz var** means merely that a
validated saved report contains a corresponding historical result; it
is never a live-health indicator or buy/sell recommendation.

## 2027 readiness and hardening

The browser's BIST100 technical JSON parser previously rejected all
`as_of` dates beyond 2026-Q4. That check is removed: only syntactically
and internally consistent historical dates are checked in the browser.
The **backend's independent source-reviewed quarterly roster loader**
still rejects 2027-Q1 saved reports until a separately verified
`bist100_constituents_2027q1.json` is present. Therefore the browser
does not attempt to bypass the 2027 fail-closed source-validation gate.

## Tests and limitations

`apps/dsa-web/src/utils/sevenMarketEvidence.test.ts` exercises all
seven rows with no evidence, the difference between 100-member BIST
scope and single-symbol offshore smokes, partial failure, manipulated
counters, duplicate markets, wrong sample currency/ticker, stale
claimed sample sessions, bad OHLCV lengths and invalid dates.
`bist100TechnicalReport.test.ts` additionally checks a hypothetical
2027 date with fully consistent row/session fields (shape only; not
independently sourced 2027 real equities).

**This feature is a draft, local/browser evidence viewer**, not a
deployed production market dashboard. Persistent storage of the six-market
probe would need a separate authenticated read-only endpoint,
source/calendaring validation and explicit approved path configuration.
Do not claim six-market broad/complete coverage or real-time monitoring
from these example rows. The previous PR #19 CI finished green (8,830
offline Python tests, 4 network tests deselected, 147 critical premerge
tests, frontend green), but PR #20 must pass its own exact-head CI.
