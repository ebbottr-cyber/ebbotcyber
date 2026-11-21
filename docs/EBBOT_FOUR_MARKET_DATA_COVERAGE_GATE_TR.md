# EBBot — Four-market equity data completeness gate (review only)

This gate checks **evidence, not trading readiness** for Türkiye/BIST (TR), US,
Germany/Xetra (DE), and Hong Kong (HK). It is independent of draft PR #58
(universe collectors) and PR #59 (Xetra candidate manifest), so it can be
reviewed on current `main` without silently merging those large draft stacks.

## Exact limits

- Baseline: `apps/dsa-web/public/stocks.index.json`, with all active
  `stock` and `etf` entries in the four selected markets. No Top-100 cutoff.
  Benchmark indexes and inactive rows are **not** stocks. CN/JP/KR/TW are
  excluded from the four-market report, not deleted from the repository.
- Other inventories can be attached using repeated `--stocks` arguments.
  A catalog/company-directory code is a **candidate**, not a verified
  exchange-tradable symbol or broker entitlement.
- Dated source rows and genuine, separately obtained daily OHLCV CSV files
  are optional evidence. The tool **does not download, manufacture, or
  infer prices or missing trading days**.
- Every ticker is counted; no instrument-count cap. Default stdout prints
  first 10 examples per failure type to avoid huge CI logs; `--report-json`
  emits **every missing, stale and insufficient symbol** in an exclusive-new
  file. A single file is capped at 64 MiB; split large historical datasets
  into multiple files and repeat `--bars`.
- Minimum history is **250 observed bars** per symbol by default. The latest
  observed bar must be within **7 calendar days** of the UTC audit date.
  These configurable heuristics do not prove correct market session calendars
  or absence of missed sessions/holidays.
- No authoritative current full-exchange listing, source license, provider
  ticker/ISIN mapping, real-time pricing, exchange-session completeness,
  Turkish broker entitlement or execution is certified here. Consequently,
  **`--strict` always blocks release** (exit 2) even if all supplied CSVs
  appear internally consistent. Never reinterpret a passing test as market
  data completeness.
- No API keys, network calls, API orders, journal changes, SQLite writes,
  schedule, strategy trading, portfolio positions, paper fills or real orders.

## Commands (repository root)

Basic offline evidence report on the *current branch*:

```powershell
python -m scripts.audit_ebbot_market_data_coverage
```

Include explicitly sourced and reviewed **local** market inventories, if
available (examples from the separate draft collector; do not imply that
the files exist in `main` or on another PC):

```powershell
python -m scripts.audit_ebbot_market_data_coverage --stocks "$HOME\EBBotPaperData\kap-bist-all.csv" --stocks "$HOME\EBBotPaperData\xetra-candidates.csv"
```

Historical OHLCV input format, one row per **real observed completed trading
session**, with required header:

```csv
market,symbol,session,open,high,low,close,volume,source,currency
tr,THYAO.IS,2026-11-20,300,305,295,303,123456,approved_historical_feed,TRY
```

The example line is **synthetic documentation**, not a market price and must
never be put into a production evidence file. Only import records obtained
under appropriate actual provider license and operator review. The
`source` label is unverified metadata, not a license certificate.

To preserve the full missing-symbol list in a new file and require a
fail-closed exit code:

```powershell
python -m scripts.audit_ebbot_market_data_coverage --stocks "$HOME\EBBotPaperData\kap-bist-all.csv" --bars "C:\ApprovedMarketData\tr-daily-2026.csv" --report-json "C:\ApprovedMarketData\ebbot-coverage-audit.json" --strict
```

`--report-json` refuses to overwrite an existing file. Input files cannot
be symlinks. Invalid, duplicate, future-dated, non-finite or inconsistent
OHLCV records fail closed (exit 1). Exit 0 in default audit mode means **the
audit ran**, not **the market data are complete**. `--strict` exit 2 means
release remains blocked.

For reproducible offline unit tests:

```powershell
python -m unittest discover -s tests -p 'test_ebbot_market_data_coverage.py' -v
```

## Follow-up dependencies (not magically completed by this PR)

1. **TR:** KAP company identifiers vs actual active BIST listings, licensed
   daily OHLCV, market calendar and the dated 100-member BIST100 roster.
   The 18-Nov-2026 local collector reported 803 KAP candidate codes but
   zero verified BIST daily quote sources; those local raw files are not
   embedded here.
2. **US/HK:** Reconcile legacy index records against dated authoritative
   exchange catalogs, corporate actions, inactive/delisted names and
   provider-symbol mappings. Legacy counts alone cannot certify coverage.
3. **DE:** Draft PR #59 contains a 19-Nov-2026 official-derived Xetra
   candidate manifest of 1,750 symbols with ISIN checks; validate fresh
   exchange identity, provider mappings and licensed actual OHLCV separately.
4. **All markets:** Obtain actual approved history, detect session/calendar
   gaps using vetted market calendars, independently check FX/currency,
   licensing, timestamp continuity and documented Turkey broker access.
5. **Crypto:** Binance Spot/Futures catalog and quote-quality work in draft
   PR #58, and Solana discovery, are **separate domains**; their snapshot
   counts must not be presented as four-market equity price coverage.
6. **Integration:** Independently review PR #58/#59 and this small audit PR
   against current `main`, run complete backend/React/Windows regression,
   enforce branch protection and obtain explicit deployment approval.
   Neither draft is authorized to enable paper/live trading.

**Release status: BLOCKED.** The gate is intentionally useful before
licensed price data are available, and remains honest about missing inputs.
