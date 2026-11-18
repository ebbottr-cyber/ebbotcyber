# Archived CI contracts (V12) — test fixtures, not automation

The prior full-backend CI gate in the Strategy Lab V11 stack uncovered
historical regression tests that still read workflow files under
`.github/workflows/`. EBBot deliberately archived these files in
`workflows_disabled/*.yml.disabled` to leave automatic daily analysis
and old release workflows **off**.

This PR updates only historical test fixture paths to read archived
workflows. Those snapshots remain parseable YAML for regression assertions
without being executable GitHub Actions workflows.

It also restores a non-secret `.env.example` from the existing integration
work, containing optional disabled examples for 16 AI providers and safe,
nonoperational SearXNG settings. No API keys, passwords, sessions,
wallets, or market execution are enabled.

The added `tests/test_disabled_workflow_archive_contract.py` checks that:
- historical CI/daily/Docker workflow files exist ONLY under the
  disabled archive, not as active equivalents;
- the active GitHub workflows do not contain a `schedule` trigger;
- example environment secrets are not assigned real values.

A manually triggered PR check is defined in
`.github/workflows/archive-contracts-v12.yml`. It runs when a PR targets
`main`, **without any automated periodic run or activation**.
This check is a focused contract regression, not a replacement
for the whole repository's backend test suite.

Other known unrelated issues (e.g. language rendering expectations) still
require independent debugging. **Do not silently skip tests** to make CI
green. Keep this PR draft until actual GitHub test evidence is reviewed.

Rollback is simply to close the PR; the active workflows, CLI commands,
pricing providers, brokers, and paper/live trading paths are unchanged.
