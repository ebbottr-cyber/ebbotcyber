# EBBot final seven React regressions — review

**2026-11-20 — stacked draft on PR #99, no release**

Source baseline: [GitHub Actions 44777662257](https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/44777662257): 1,490 passed, 7 failed, 2 skipped; **an additional collection error** because Vitest tried to load the Node-only `tests/pwa-smoke.test.mjs`. Native `npm run test:pwa` separately passed 9/9.

## Root causes and changes

1. **Meme Coins (2 tests)**: page production copy is Turkish, while no-provider legacy Vitest context defaults to Chinese. The two production UI assertions now explicitly enable `VITE_EBBOT_TURKISH_TEST_MODE=true` and clean up the temporary test-only setting. No strategy, scan enabling, trading mode, API or data changes.
2. **Decision Signals (1)**: revalidated signal `#90` has a fixed old creation timestamp. The **default timeline is 90 days**; it is incorrect to demand an older signal be visually inserted into the current timeline merely because a refresh returned it. Test now verifies latest data reload and no out-of-window timeline point. Production date boundaries remain unchanged.
3. **Sidebar (1)**: new Overview and Xetra links legitimately appear. The test checks the actual required relation, **Chat immediately followed by Screening**, and the continued presence of Portfolio / Decision Signals instead of relying on absolute array positions. None of the routes was removed.
4. **Notification Test (1)**: Turkish channel label is `E-posta`, not `Email`. Test asserts correct Turkish label and absence of the English one. Notification send behavior unchanged.
5. **Theme bootstrap (1)**: actual default `index.html` theme is light and explicitly honors saved dark/light. Test source assertion now expects the actual light default. No theme policy changed.
6. **UI governance (1)**: native HTML `title` found in language toggle and Desktop Update indicator. Removed redundant titles from language status/toggle; desktop update retains tooltip text as accessible `aria-description` on its icon button. This passes policy without weakening the prohibited-title check.
7. **Test collection**: excluded exactly the Node-only PWA smoke from Vitest's test discovery. `npm run test:pwa` is kept and executed separately; no application tests are excluded.

## Validation / release restrictions

Dedicated GitHub Actions checks focused tests, full Vitest regression set, production lint/build and PWA with Node. **Do not merge/release based on this draft alone**: browser E2E, backend/integration, actual market-data availability, security and operational signoff are distinct gates. No scheduled jobs, deployment, database changes, live orders, FX valuation or auto-trading introduced.

Rollback: close this draft PR or revert these commits; production `main` stays unchanged.
