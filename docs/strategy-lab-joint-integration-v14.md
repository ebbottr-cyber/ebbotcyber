# V14 — Combined Strategy Lab and backend-remediation integration candidate

This **draft integration candidate** is based on V11 draft PR #49, and
incorporates the non-overlapping **file contents** of V12 (#51) and
V13 (#52) into a single separate review branch. The existing changelog
was carefully joined instead of replaced. The V12 and V13 PRs are
**still separate, draft, unmerged**: copying reviewed code blobs to this
candidate does not mean they were merged into main or into their parent
branches.

## Inputs

- V1–V11 Strategy Lab stack: #30 → #32 → #34 → #37 → #42 → #44 →
  #46 → #48 → #49.
- V12: #51 corrects archived CI contract paths and restores safe
  `.env.example` examples, without re-enabling retired workflows.
- V13: #52 ensures Turkish stock-analysis prompts select English
  *market-context scaffolding* with an explicit Turkish output directive,
  and tests the already-existing Turkish missing-news notices.
- V11 production/readiness gates remain in force. No strategy/risk/order
  execution code was modified by the V12/V13 port.

## What the new workflow verifies

`.github/workflows/strategy-lab-joint-v14.yml` is bound only to PRs
targeting `ci/strategy-lab-release-gate-v11`. It runs four jobs:

1. Read-only audit of the original eight Strategy Lab PR dependencies
   and the two remediation PRs (#51, #52), failing closed on unknown,
   conflicting, wrong-base, closed or already-merged pull requests.
2. Combined Python contract regression for ETF random benchmark,
   V8 chronological holdout, V9 next-session paper journal, V10
   authenticated read-only import, V11 gate, V12 archive safety and
   V13 Turkish backend language.
3. React/TypeScript lint/build and Turkish-language user-interface
   regressions on the combined source tree.
4. **Complete repository backend pytest**, without exclusion/xfail,
   failure suppression, retry-as-pass or modifying trading settings.

## What a green workflow does **not** prove

- No authenticated, deployed Strategy Lab UI screenshots or end-to-end
  user session. No VPS/PC installation or persistent future-session
  observation record has been performed.
- No code review approval, nor permission to merge or deploy.
- No live broker connection, paper broker account, Solana meme-coin
  execution, automated trading, daily analysis or scheduled journal
  creation has been enabled.
- Historical ETF random-timing benchmarks and retrospective holdouts
  do not prove future strategy alpha. Forward-adjusted data is subject
  to provider revision, and prospective paper tracking needs actual
  successive future market closes.

This integration candidate is a review aid only. All underlying PRs
must be independently evaluated; if a targeted check fails, repair
the relevant source branch and rebuild this candidate. Avoid
silently changing the real trading code.

## Rollback and operation

Close the draft integration PR. No actual main-branch commit,
workflow schedule, service deployment, financial order, or journal
modification results from creating this branch.
