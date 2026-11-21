# EBBot Windows React + SQLite tentative integration — 21 November 2026

**Draft, no main merge, no app release.**

Source candidate: PR #168 `18d80ace433b97aef7e51f7219bbfe58a8fb9d54`.
Only new latest-main frozen React CI probe files are taken from `main@c95fb7f2ee63d5bee131bd59b25a38ae420d0546`; update/snapshot safety code remains from Windows candidate.

- The special Electron CI-only startup path now passes `reactProbe` to the packaged BrowserWindow helper. It must return exit code 42 only after real Turkish navigation passes; ordinary splash health returns exit 0. Both require packaged Windows, GitHub Actions, explicit CLI, and exact 127.0.0.1 backend.
- The frozen FastAPI health-only mode serves bundled React static files and canned read-only auth status **only** with the extra `EBBOT_PACKAGED_REACT_PROBE=1` opt-in; normal markets, strategies, analysis, auth sessions, scheduled jobs and orders are NOT started.
- The existing SQLite WAL snapshot, safe backups/recovery/rollback, package SHA512, signing metadata collection, Electron tests, and NSIS `--publish never` remain active in the Windows test workflow.
- The current candidate React suite has 1,526 passed and 2 pre-existing skipped tests on its previous revision. New source must be retested; earlier passing tests cannot be attributed to this commit.
- The candidate remains separated from `main`, not merged, signed, installed, or published. Main branch protection and independent review are still required. Real/paper trading, automated scans, updater and deployment remain blocked.
