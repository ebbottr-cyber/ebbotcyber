# Six-market Yahoo fallback smoke (operator-neutral)

This draft-only verification probes **one representative equity per previously supported market**, with Yahoo historical daily prices, the bot's existing Yahoo ticker adapter, calendar classification, quote currency, valid OHLCV and the existing `StockTrendAnalyzer`. It is *not* an all-market stock list, a live production data-source test, a complete provider routing test, a Turkish AI report, or an investment recommendation.

| Market | Bot input | Yahoo ticker | Expected currency |
|---|---|---|---|
| Mainland China | 600519 | 600519.SS | CNY |
| Hong Kong | HK00700 | 0700.HK | HKD |
| United States | AAPL | AAPL | USD |
| Japan | 7203.T | 7203.T | JPY |
| South Korea | 005930.KS | 005930.KS | KRW |
| Taiwan | 2330.TW | 2330.TW | TWD |

Run on a networked environment with the project's existing Python requirements:

```bash
python -m src.services.six_market_live_smoke --as-of 2026-11-15 --output six-market-report.json
```

The read-only probe exits nonzero unless all six independently pass market detection, the bot's Yahoo code conversion, market-specific verified previous-session calendar, currency, at least 60 valid daily bars, fresh last completed-session price and the **existing technical analyzer**. Every market remains explicitly listed with its status even when another fails.

The `six-market-live-yahoo` CI job runs only in draft branch `test/six-markets-live-smoke` and uploads its JSON + stderr trace as a short-lived artifact. The offline `tests/test_six_market_live_smoke.py` suite uses injected candles and calendar dates. The runner never opens SQLite, modifies production data, places orders or calls LLMs. Yahoo is only an international fallback provider here, so even 6/6 success does **not** verify regional primary sources or all stocks in each market.

Integrate separately from the in-flight BIST100 draft PR #8 after both sets of evidence have been reviewed; no automatic merge is requested.
