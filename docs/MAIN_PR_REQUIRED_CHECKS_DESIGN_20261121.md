# EBBot main PR required-check design — DRAFT, NOT ENABLED

This PR upgrades the **existing** main pull-request verifier
(\`.github/workflows/pr1-verify.yml\`) rather than introducing a duplicate
parallel CI. It is intentionally a **draft PR targeting main** so its changes
can be inspected, but no merge or GitHub settings change is authorized here.

## What the proposed workflow actually enforces (once reviewed/merged)

The main target remains \`pull_request: branches: [main]\`, with **no paths
filters**, so every future main-targeting PR will get the same four stable
job checks, regardless of which files it changes:

- \`EBBot PR / policy\`: always checks the workflow security contract and
  fail-closed result aggregator using only Python's standard library
- \`EBBot PR / backend\`: source-security and Solana anti-replay tests with
  external test sockets blocked; then the full backend
  \`pytest -m "not network"\` suite with a fixed timeout. The full suite
  **does not claim to block all outbound sockets**; tests bearing a network
  marker are excluded, and no broker credentials are supplied
- \`EBBot PR / frontend\`: locked \`npm ci\`, all Vitest tests, ESLint,
  production TypeScript and Vite build on Node 22
- **\`EBBot PR / merge gate\`**: depends on the other three jobs and runs
  **even if an upstream job fails or is skipped**; rejects any missing,
  cancelled, skipped, failed, unknown, or differently named prerequisite

The only extra event is a **push to the specific temporary audit branch** to
validate the workflow before it is considered for merging. No scheduled event,
\`pull_request_target\`, reusable workflow dispatch, cron, deployment,
broker API, order, wallet or portfolio mutation exists in these changes.

The credential scope is \`contents: read\` and every checkout disables
persisting the GitHub token. These checks are not authority to merge or
publish: humans must review source, third-party dependencies and any changes
to this YAML; PR authors can propose changes to their own tests/workflows.

## Important: GitHub protection is still OFF

At review start, GitHub showed \`main.protected=false\` and the repository
rulesets endpoint returned \`[]\`. Branch-protection administration endpoints
return **403** through the available connector. A green CI workflow does
**not** set or enforce branch-protection settings.

**Administrator follow-up after approving the design and verifying an actual
main-targeting PR check run:**

1. In GitHub, navigate to **Settings → Rules → Rulesets → New branch ruleset**.
   Target exactly \`main\`; set enforcement to **Active**.
2. Enable **Require a pull request before merging**, require independent
   approval where available, dismiss stale reviews on new changes and require
   all review conversations to be resolved.
3. Enable **Require status checks to pass**. Use the **observed, actual**
   GitHub status context \`EBBot PR / merge gate\` after a successful
   main-PR run; if GitHub displays the workflow-qualified context or a
   different check name, use that **exact** context. Prefer requiring the
   individual policy/backend/frontend checks as defense in depth only if
   they are all actually emitted consistently.
4. Disable **force pushes** and **deletions** for main, and verify bypass
   actors and admin privileges are not silently exempt.
5. Confirm a proposed unreviewed main push or a failing/never-emitted
   required check is actually rejected. Record the effective ruleset ID,
   branch target, enforcement, required contexts, review policy and bypass
   settings through an **authorized GitHub administrator**.
6. Do not use \`turkish-report-verify.yml\`, the Solana promotion workflow,
   or branch-only audit job names as universal required checks without
   confirming which PR paths cause them to run. Those jobs are selective,
   and a skipped check can leave PRs waiting indefinitely.

This PR does **not** activate branch protection. Its self-test branch check
will not satisfy a future required main-PR policy by itself.

## Existing limitations after main CI gates

A successful main PR gate **does not** prove safe trading or permission to
use market data: independent licensed BIST source access, publication across
distinct real market days, live executable quotes, real broker credentials,
paper trading readiness, Solana execution approvals, Windows installer
signing and operations release policies are all separate gates.

Importantly, the current \`main\` frontend does not expose the newer
\`test:pwa\` script in \`apps/dsa-web/package.json\`; this proposed base-main
workflow does **not** label an unrun PWA check as passed. The richer PWA
checks have separately passed in PR #130's temporary integration of
\`main + PR #122\`. Any future main integration must explicitly add and
validate those checks as part of the reviewed PR.

**No main merge, no repo ruleset modification, no scheduled jobs, no
orders/fills, no live/paper trading.**
