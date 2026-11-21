# Strategy Lab V11 — cumulative release readiness (read-only)

V11 does **not** add a strategy, order execution, trading automation, or
production deployment. It is an audit and CI gate for the existing stacked
research and prospective-paper drafts. Existing isolated green jobs are NOT
sufficient proof that the combined feature can safely ship.

## Dependency chain

Merge **only after** each base PR is green and independently reviewed, in
this order; never force-merge a conflict or use auto-merge:

| PR | Work | Expected target |
| --- | --- | --- |
| #30 | Random-timing benchmark core | `main` |
| #32 | Rotation timing bridge | `feat/random-timing-benchmark-v1` |
| #34 | Strategy Success Lab API/UI | `feat/rotation-random-benchmark-bridge-v1` |
| #37 | Turkish UI coverage | `feat/strategy-success-lab-v1` |
| #42 | Dual-provider ETF data consistency | `fix/turkish-ui-type-coverage-v1` |
| #44 | Chronological walk-forward / holdout | `feat/provider-consistency-v7` |
| #46 | Manual opt-in prospective paper journal | `feat/strategy-lab-walk-forward-v8` |
| #48 | Read-only paper dashboard and operator wrapper | `feat/strategy-lab-prospective-paper-v9` |

The V11 **draft** is a separate additional PR targeting #48's head branch.
`scripts/check_strategy_lab_stack_v11.py` calls GitHub PR REST GET endpoints
and validates all eight dependencies' head/base branches, open/unmerged
status and current mergeability. It **fails closed** on conflicts,
unknown/unavailable metadata or missing PRs. Integration mode permits drafts
(so developers can verify a stack); `--release` also blocks drafts and
non-clean review states. This check NEVER merges or modifies PRs.

A prior targeted workflow conflict in PR #34 was caused by independently
adding `.github/workflows/strategy-lab-targeted.yml` to both #32/#34.
It was aligned to the #32 version on #34. PR #37 keeps its separate
V4 regression workflow at `.github/workflows/strategy-lab-v4-regressions.yml`
to preserve Turkish/front-end and actual ETF price smoke coverage.

## Required CI verification

`.github/workflows/strategy-lab-release-v11.yml` runs on V11's PR:
1. **Stack graph audit** — actual GitHub mergeability and target branches;
2. **Cumulative backend contracts** — Python random benchmark, real rotation
   bridge, Strategy Lab API, price-provider reconciliation, OOS/holdout,
   prospective paper and journal/import/operator guards;
3. **Cumulative frontend contracts** — Strategy Lab, paper import, Turkish
   regression tests, TypeScript typecheck, lint, production build;
4. **Full backend regression** — `python -m pytest -q` for the complete
   repository, without `continue-on-error`, test exclusion or silently
   treating existing baseline failures as passes.

The full backend suite has had unrelated failed assertions on prior PRs.
Do not promote or merge this stack merely because focused checks pass.
Inspect the full failure list, distinguish pre-existing failures from actual
regressions, and repair/review in narrowly scoped PRs. Tests must be rerun
on the actual latest merge candidates, not just on early feature branches.

## Pre-deployment / paper operations checklist

- [ ] Main-branch conflicts and full CI resolved, and code reviewed.
- [ ] Authenticated UI screenshot and real private journal import verified.
- [ ] Durable PC/VPS online with known timezone, persistent journal directory
      **outside the repository**, appropriate ownership/backup and provider
      access; a GitHub Actions sandbox is not a reliable multi-day journal.
- [ ] `ADMIN_AUTH_ENABLED=true` set through the approved admin config and
      session login validated before journal upload; never upload a personal
      journal to an unknown remote EBBot installation.
- [ ] Real provider data checked as a **completed trading session**; do not
      fabricate a time-series from retrospective close history and call it
      forward-paper evidence.
- [ ] Perform a **preview** before operator-authorized `--commit`. The
      observer starts in cash at virtual equity 1.0, no retrospective P&L.
- [ ] Validate actual notification delivery with the chosen connected
      notification provider if failure alerts are requested. Synthetic/mock
      delivery tests are not evidence of real push delivery.
- [ ] Only with separate explicit approval configure an operating-system
      daily task after the exchange close; V11 neither schedules nor starts it.
- [ ] Collect and evaluate many consecutive new market sessions; don't
      promote real orders on past holdout/randomized results.

The experiment is currently **single Chinese A-share ETF vs cash**. It
does NOT establish coverage or broker accessibility for Türkiye, nor
validate Solana meme-coin, Turkey equities or other assets. Existing holdout
results showed inconsistent edges and no basis for automated live trades.

## Local audit

```bash
# Read-only current PR check, requires network GitHub access. Use a GitHub
# read-only token for private repo API access if needed.
python scripts/check_strategy_lab_stack_v11.py

# Strict pre-release gate (currently expected to fail while PRs are drafts):
python scripts/check_strategy_lab_stack_v11.py --release

# Offline self-test; no network or order API:
python -m pytest -q tests/test_strategy_lab_release_gate_v11.py
```

No public API, application runtime, portfolio order path or existing
scheduler is changed by this V11 release gate. Screenshots are not provided:
this PR adds no user-facing UI, and the prior paper panel is still awaiting
deployment and authenticated visual verification.
