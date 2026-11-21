# EBBot Main + React + Windows four-route combined draft — 2026-11-21

**Strictly DRAFT. This is not a published installer or an instruction to merge to main.**

Inputs:
- Latest main: `885d4ff9a3c01d467853febb5f28303ff93638f2`
- Tested Windows/React/SQlite branch PR #172: `fb1e4e9fb4a13ebbd635ded97f8c4f604197a94c`

This draft intentionally incorporates the latest main's additional **read-only** packaged React navigation to four pages: Portfolio, AI Signals, Screening and Settings, while preserving offline frozen health-only API, SQLite WAL consistent backup/crash recovery, safe restore, stage/rollback rehearsal, no-publish NSIS and EBBot identity/updater restrictions.

The packaged CI Electron smoke still **does not** click, perform or submit trade, strategy-run, analysis, scanner, scheduler, login, configuration-save or brokerage actions. It only uses a frozen synthetic local web fixture, `127.0.0.1`, `GITHUB_ACTIONS=true`, packaged Windows and exact diagnostic arguments.

**Localization policy:** preserve the comprehensive Turkish UI entries from the candidate, include all three `layout.nav.memeCoins` fallback entries from main, and reconcile four Turkish page-heading/title entries without duplicate keys. Do not silently replace the full candidate locale dictionary with the main's shorter dictionary.

**Verification requirements before *any* later merge consideration:**
1. Electron unit tests plus real Windows PyInstaller/NSIS `--publish never`, frozen backend health and Turkish React 6-route navigation test.
2. All 123+ React Vitest suites, eslint and TypeScript/Vite production build.
3. Whole backend selected via `pytest -m 'not network'` and SQLite safety contracts.
4. Explicit main SHA, independent signing/SmartScreen and per-device install/upgrade + migration review; no protections currently on the main branch.

This isolated Git draft may use a two-parent commit to record both sources, but it must not update `main`, issue a GitHub release, upload installer bytes, enable updater/scheduler, use real credentials, or perform paper/live trading.
