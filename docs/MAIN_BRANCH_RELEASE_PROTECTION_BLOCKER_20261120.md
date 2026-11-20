# EBBot — \`main\` branch release protection is NOT configured (2026-11-20)

**Status: BLOCKED — no deploy, no trade, no PR merges performed by this audit.**

## Actual evidence reviewed

- GitHub repository: \`ebbottr-cyber/ebbotcyber\`, public, default branch \`main\`.
- Last pinned \`main\` snapshot: \`68f9d1652f81a3edf70784526d18578c772fe922\`.
- GitHub REST \`GET /repos/ebbottr-cyber/ebbotcyber/branches/main\`: \`protected: false\`.
- GitHub REST \`GET /repos/ebbottr-cyber/ebbotcyber/rulesets?includes_parents=true\`: \`[]\` (no ruleset summaries returned).
- GitHub branch-protection administration endpoint returned **403 Resource not accessible by integration**. We **cannot** infer which required reviews/status checks/bypass settings are enforced, or change the settings with this connector.
- PR #122 and PR #130 are DRAFT audit/integration work; passing unit/regression tests do **not** grant production release, real orders, or paper trading.
- The existing full GitHub Actions test result from a pinned commit only applies to that commit; new pushes and new rules require new evidence.

## Administrator-only GitHub action (not done by this PR)

In the repository's own GitHub UI, an administrator should visit **Settings → Rules → Rulesets**, add an **active branch ruleset targeting exactly \`main\`**, or use the available classic branch-protection section if appropriate to the repository.

For \`main\`, verify all of the following in the effective policy:

1. Require a pull request before merging; require review from at least one qualified independent reviewer and dismiss stale approvals when code changes.
2. Require all relevant **real, successful, non-skipped** backend, React/TypeScript/PWA, market-data and release safety status checks for the **exact candidate commit**. Select status-check names from jobs actually published by GitHub; do **not** copy a guessed check name from documentation.
3. Require resolution of review conversations; do not allow ordinary users to bypass required reviews/checks.
4. Block force pushes and branch deletion. Review administrator bypass permissions explicitly, including organization/automation actors.
5. Validate that the rule targets the **effective** \`refs/heads/main\` branch, that enforcement is active (not merely evaluate/disabled), and that the rules really prevent an unreviewed direct push.
6. Keep automated orders, paper/live trading, background scans, wallet access, release publication, and PR merge disabled until a separate, explicitly approved procedure addresses data provenance, licenses, operations, and security. **Do not add trading credentials** to these audit workflows.

The audit cannot modify these controls. After an administrator makes changes, **re-read GitHub's actual branch protection/ruleset details** under an admin-authorized account. This script only reads public metadata and **will remain release-BLOCKED even when \`protected\` changes to true**, because it cannot prove effective review and check settings.

## CI meaning

\`.github/workflows/ebbot-main-protection-audit-only.yml\` triggers only on the dedicated audit branch push, runs eight no-network regression tests, reads the actual public GitHub metadata once, and publishes a JSON report with a **BLOCKED** verdict. A green *audit job* means the blocker was successfully identified; it is **not** a release approval or a claim of an effective branch-protection rule.

A moved \`main\` commit or PR #130 head produces \`BLOCKED_PINNED_SOURCE_MOVED\` until independently reviewed. No commit is pushed to \`main\`. The new workflow has read-only content permissions, never has a release/deploy/merge job, and never starts schedules, trades or portfolio writes.

### Remaining blockers beyond GitHub protection

A licensed independently verified BIST second market-data source is not connected; multiple real independent market publication dates and long-term data reliability are not proved; Windows installation packaging and release signing have their own gates. Even after policy configuration, treat prices as indicative/delayed rather than executable.


## Exact integration CI evidence verified independently

The successful, **completed** main+PR122 integration GitHub Actions run is:

- https://github.com/ebbottr-cyber/ebbotcyber/actions/runs/44813551015
- \`head_branch=audit/ebbot-main-pr122-solana-replay-full-20261120\`
- \`head_sha=f5c6dbe9a201d7f3a7df94b600697f869514c70c\`
- Under-test \`main=68f9d1652f81a3edf70784526d18578c772fe922\`, PR #122 head \`f73ce5d7fcea9255822239420ed61d12521e3493\`.

The run completed successfully and its three original jobs completed successfully:

1. \`Pin GitHub main and PR122, no-commit merge-tree, NO release\` (merge-tree and metadata preflight).
2. \`FULL React/PWA on actual ephemeral main plus PR122 joined code\` (1,524 passed, 2 skipped; lint, TypeScript/Vite build and 9 PWA passed).
3. \`FULL backend on actual ephemeral main plus PR122 joined code\` (150 focused passed; 9,327 full offline pytest passed, 4 deselected).

\`scripts/audit_pinned_integration_ci_evidence.py\` uses original, read-only GitHub REST run + jobs + PR122 + PR130 + \`main\` evidence. It enforces *exact* pinned run ID, head SHA, PR state, branch, run attempt, and the three job and critical test-step completions. A successful \`actions/runs\` record is not sufficient if any of the critical jobs were skipped, failed, cancelled, duplicated or run at another SHA. The audit fails closed on bad evidence.

The GitHub workflow is **an audit-only push workflow for a feature branch**. Its job names should **NOT be blindly marked as required main-PR status checks**: they may not be produced for each prospective merge commit. An administrator should identify or create a persistent, read-only CI workflow that runs on every PR targeting \`main\`, then select its real observed stable job names as required checks. Enforce these alongside code review, force-push and bypass safeguards in GitHub Settings.

**Critical distinction:** These verified tests say that the *pinned code combination* passed an offline test suite. They do not prove actual branch protection, licensed BIST data access, live quote accuracy, executable prices, packaged Windows installer, portfolio performance, or readiness to place any trades. Production release and all paper/live trading remain blocked.
