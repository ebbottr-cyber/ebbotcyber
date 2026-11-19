# Archived workflow verification and safe CI contracts

The repository intentionally moved some historical GitHub Actions files to
`workflows_disabled/*.yml.disabled`. These are not live workflows. In particular:

- `00-daily-analysis.yml.disabled` is **not** automatically scheduled.
- `ci.yml.disabled` is **not** an executable CI workflow.
- Historical Docker publication workflows remain inactive.

Legacy tests still exercise the shape of archived workflow definitions as static
reference material, but they must never be interpreted as verification of an
**active** schedule or CI job. Tests also assert that these archives do not
reappear under `.github/workflows/` and that active workflows have no schedule.

Current executable PR checks use `.github/workflows/pr1-verify.yml` and
`.github/workflows/meme-radar-verify.yml`. They are distinct from archived
matrix-sharded CI; do not claim that old sharding tests validate the active job.

The notification environment table generator now reads the **archived**
daily-analysis definition, preserving the historical table for reference. It
does not enable that automation. The full backend test suite still has separate
missing `.env.example` and Turkish report compatibility issues until those
areas are repaired independently.

Do not rename `*.disabled` files to `*.yml` merely to fix a path error:
that would reactivate schedules or publish jobs.
