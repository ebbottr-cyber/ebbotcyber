# EBBOT-CYBER — localization and integration notes

Upstream: [ZhuLinsen/daily_stock_analysis](https://github.com/ZhuLinsen/daily_stock_analysis). Preserve license and attribution.

## Implemented

- Turkish (`tr`) frontend UI language, English fallback, browser language detection and language switcher.
- Partial Turkish UI copy, including navigation, data center and common actions.
- Turkish stock analysis language recognized by `src/report_language.py` (`tr`, `tr-TR`, `Turkish`, `Türkçe`).
- Core Turkish report headings, trade signals, confidence and trend labels; remaining report labels fall back to English.
- Turkish output instructions in stock analyzer system and user prompts, preserving JSON keys, ticker symbols and numeric data.
- Basic regression tests in `tests/test_turkish_report_language.py`.
- `tr` accepted by stock analysis and market review API request schemas and the frontend `ReportLanguage` type.
- Offline Nasdaq AAPL routing and Turkish request contract tests in `tests/test_nasdaq_turkish_smoke.py`.

## Still pending

- End-to-end review of other report generators, notifications and all language-specific branches. Not every report producer is guaranteed to emit Turkish.
- Finish all screen-specific UI translations and strategy labels.
- Local Python tests, frontend build and runtime validation have **not been executed** in this integration session.
- Validate Turkish output across other market-review and notification report generators; this is not yet an end-to-end guarantee.
- Nasdaq live data check, BIST support and ETRE integration.

## Local verification (no GitHub Actions quota)

```sh
python -m pytest tests/test_nasdaq_turkish_smoke.py tests/test_turkish_report_language.py tests/test_report_language.py tests/test_report_language_prompt_directives.py tests/test_analyzer_prompt_language.py -q
cd apps/dsa-web
npm ci
npm run build
```

Configure the application using the original upstream documentation; keep secrets in untracked local files. Do not enable previously disabled workflows until explicitly needed.

The existing crypto and Solana Hype systems are not part of these changes.

## Nasdaq validation milestone

1. Run the offline AAPL test suite above without enabling GitHub Actions.
2. With a configured local API runtime, verify that the analysis request schema accepts:

```json
{"stock_code":"AAPL","report_type":"detailed","report_language":"tr","notify":false,"async_mode":false}
```

3. Confirm that Yahoo Finance actually supplies price history for AAPL (network required); a mock-only test does not prove live availability.
4. Configure an authorized AI generation backend and verify the response keeps numeric values and returns Turkish narratives. Never commit credentials.
5. Examine risk warnings, stock name, report persistence and the web UI for unintended Chinese text before declaring the milestone complete.

No live Nasdaq market call or LLM inference has been executed in this session.
