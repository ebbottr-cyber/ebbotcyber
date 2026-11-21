# EBBot PR #178 — Read-only CI provenance and release/merge security review

**DRAFT ONLY**. This is an evidence report, not a release or production deployment.

The parent PR #178 has a real two-parent Git commit `9ac204944df962f1043296561f7907d42eea080c` based on a frozen `main@885d4ff9a3c01d467853febb5f28303ff93638f2`. GitHub's last observed `main.protected=false`. No main commit or branch protection settings have been changed.

Three CI runs, each pinned to that **same** source commit, are required:
- React full, focused, ESLint/Vite: [44887061797](https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/44887061797).
- Real Windows PyInstaller, NSIS `--publish never`, 6 Turkish navigation checks, SQLite, identity and signing *inspection*: [44887061763](https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/44887061763).
- Backend `pytest -m 'not network'` and fail-closed job: [44887061769](https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/44887061769).

The audit verifies precise GitHub Actions run id/name/head SHA/status/conclusion, the **entire expected job set**, exact parent SHA order, and that PR178 remains draft and unmerged. Run-level green cannot mask skipped or cancelled **jobs**, changed branches, different commit, incomplete pages or a failing test job. The two preexisting React skipped **test cases** are explicitly disclosed and require separate review. `-m 'not network'` is marker selection, **not** an air-gapped network guarantee.

`scripts/audit_ebbot_pr178_release_evidence.py` always returns a blocked release result, including if all CI is green. GitHub Actions intentionally has a red terminal release-deny job. This gate is **not** a proposed required check to merge the PR: it is a separate permanently red no-release warning that prevents false readiness claims.

Blockers still require human administrator/security authorization: GitHub main branch rules with mandatory checks/reviews; valid code signing and certificate provenance, SmartScreen reputation, Windows install/upgrade/uninstall device validation, preservation of real user SQLite data including locked-file recovery, third-party licenses and distribution policy; two existing skipped React cases. None is made true automatically based on a CI pass.

**No commands here** sign, install, upload executable files, modify `main`, start a scheduler, transact with brokers, or enable simulated/real trades.
