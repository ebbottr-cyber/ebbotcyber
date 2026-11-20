# UI language no-provider fallback — React release triage

**20 November 2026 | draft review | parent PR #92**

The previous full-suite GitHub Actions run ([44773582963](https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/44773582963)) reported **361 failed / 1,134 passed / 2 skipped** out of 1,497 tests. An earlier conversational status mentioned 358 failures; the run artifact itself is authoritative and reports 361.

### Root-cause evidence

The regression log shows repeated failures looking for legacy Chinese UI texts in:
- Portfolio: 88 failed-test headings
- Settings: 59
- Home: 57
- Chat: 19
- AlertRuleForm: 16

Many tests instantiate these components without `UiLanguageProvider`. `useUiLanguage()` therefore reads a hardcoded `fallbackContext.language = 'tr'` even in Vitest compatibility mode, while legacy fixtures expect `zh`. This is a mismatch between the fallback language and the existing test-only `getRuntimeInitialLanguage()` policy introduced in the preceding drafts. The only production policy remains **Turkish-only**.

### Changes

- For the provider-free fallback, choose **Turkish in production**, but **Chinese only in explicitly isolated legacy Vitest mode**. This uses the same already-existing `shouldForceTurkishUi()` flag; no new configuration or runtime override.
- Translate the fallback `t()` lookup from the same resolved language, so label and reported language cannot disagree. Compute at read time to allow test-only flag changes.
- Fix a separate wrong Vitest mock property in Portfolio tests: `portfolioApi.refreshFx` had accidentally been wired to the broker-list mock instead of `refreshFx`, and `listImportBrokers` was omitted. This only changes tests; the actual service code is unchanged.
- Add explicit provider-free production and legacy contract tests.

### Safety & validation

No market strategies, prices, FX valuations, risk calculations, API routes, credentials, database migrations, background workers, or real orders are modified. This patch does **not** force Chinese anywhere in production.

A passing focused test and production build cannot replace the full suite, real-browser checks, or a complete release audit. The review workflow separately reports full React failures; do **not** merge/release based on focused green results.

Rollback by closing the draft or reverting the PR commits; `main` is unchanged.
