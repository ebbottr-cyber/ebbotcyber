# V13 — Turkish backend report prompt and disclosure compatibility

The full backend gate on the [V12 archive test PR](https://github.com/ebbottr-cyber/ebbotcyber/pull/51) exposed **eight** language regressions after its archived-path fixes: one Turkish stock-analysis system-prompt case, one supported-language disclosure coverage case and six parametrized Turkish disclosure renderings.

## Root cause

`src.report_language.SUPPORTED_REPORT_LANGUAGES` includes `tr`, but
`src.market_context.get_market_role` and `get_market_guidelines`
previously treated any language other than `en`/`ko` as Chinese.
For Turkish, the actual market-specific role/guidelines could inject
Chinese text into an otherwise English-scaffold Turkish analysis prompt.

The existing `src.services.empty_news` **already had** correct
explicit Turkish messages for missing news sources and zero news
results, but `tests/test_notification_empty_news_disclosure.py`
was still missing the `tr` branch of its expected-output table.
The test mismatch did not justify removing Turkish as a supported
language, or replacing Turkish with an English/Chinese fallback.

## Narrow fix

- Reuse the existing **English financial-market context** for `tr`
  (matching the already-English `ko` scaffold). Keep the Turkish
  output directive and official stock names/tickers unchanged.
- Add Turkish missing-news strings to the existing explicit report test
  mapping. Runtime notification/disclosure behavior is **not** changed.
- Add independently parametrized language regression coverage for the
  market families CN/HK/US/JP/KR/TW, confirming `zh` remains Chinese,
  `ko` remains English context and `tr` uses the English context
  with a Turkish output directive.
- Dedicated GitHub Actions workflow runs the relevant report tests
  **and complete backend pytest**, without test skips or suppression.

## Deliberate limitations

This branch is based on **draft PR #51**, not on the V11 Strategy Lab
stack. The 11 Turkish TypeScript mismatches visible on the V12 base
are already addressed by **draft PR #37** and pass on the composite
V11 frontend contracts. Do **not** duplicate the frontend fixes in
this PR just to turn a base-branch check green.

No changes to stock/ETF selection, market providers, strategy/risk
parameters, trade execution, broker connections, notifications
delivery, or scheduled analysis are included.

Both the V12 and V13 draft PRs remain unmerged until independent
review and the complete combined-stack CI/deployment gate passes.
Historical random benchmarks and prospective paper observer remain
research-only. The "all backend tests passed" claim requires an
actual successful run of `python -m pytest -q` at this branch HEAD.

## Verification

```bash
python -m pytest -q tests/test_turkish_market_context.py \
    tests/test_analyzer_prompt_language.py \
    tests/test_notification_empty_news_disclosure.py \
    tests/test_turkish_report_language.py \
    tests/test_report_language.py
python -m pytest -q
```
