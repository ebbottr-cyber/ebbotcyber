# SQLite pre-merge snapshot, verification and rollback runbook

**Status:** pre-release candidate for Draft PR #11. This document does **not**
authorize deployment, schema migration, an automatic merge or live trading.

## Why this gate exists

`DatabaseManager` initializes/migrates schema on startup
(`src/storage.py`). The PR #2 repair protects `intelligence_items` against
unsafe legacy rebuilds and restores known secondary indexes without rewriting
an already migrated table. Nevertheless, a successful CI test on an isolated
SQLite database is not permission to run a first migration against real data.

The runtime database comes from `DATABASE_PATH` and defaults to
`./data/stock_analysis.db` (`src/config.py`). SQLite WAL is enabled by
default. **Never copy just a live `.db` file as a backup while writers are
running; committed transactions may still be in `-wal`.** Use the SQLite
online backup API, or make a backup after all writers have stopped.

## Release gates — all mandatory

1. Record exact candidate commit SHA and verify current frontend/backend CI,
   including `tests/test_storage.py`,
   `tests/test_market_sqlite_pr2_integration.py` and
   `tests/test_sqlite_snapshot.py` and
   `tests/test_sqlite_migration_rehearsal.py`; check all skips and warnings.
2. Review PR #2, #8, #9, #10 and #11 content reconciliation. Keep one approved
   integration PR; do not blindly merge multiple overlapping draft PRs.
3. Identify the actual resolved `DATABASE_PATH` on the target machine and
   confirm it is the intended instance. Do not use an assumed filename or
   GitHub runner database as a substitute.
4. Confirm owner/operator approval, a maintenance window, paused scheduled
   analyses/writers and enough free space. Record application/worker state.
5. Create a new, access-controlled backup **outside the repository** (ideally
   another volume/off-host), verify SQLite integrity, record the JSON summary,
   and retain a second protected/off-host copy. Never commit DBs or backups.
6. Restore a **copy** of that backup into an isolated staging path and test
   application startup/migration there, never against the only backup or the
   live `DATABASE_PATH`. Compare relevant row counts, schema/indexes,
   historical bars and representative read-only BIST screening output.
7. Require explicit human review of staging results and rollback readiness
   before any live migration / `main` merge. Do not run orders in validation.

## Backup and verify (PowerShell, repository root)

Change both paths for the real machine. The target directory must already
exist; the destination filename must **not** exist. This example performs no
production migration or order activity.

```powershell
$db = (Resolve-Path ".\data\stock_analysis.db").Path
$backupDir = "C:\EBBOT-backups"       # select a secure directory outside the repo
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backup = Join-Path $backupDir "stock_analysis-$stamp.sqlite"

python .\scripts\sqlite_snapshot.py --source "$db" --output "$backup"
if ($LASTEXITCODE -ne 0) { throw "SQLite snapshot failed. STOP." }

python .\scripts\sqlite_snapshot.py --verify-only "$backup"
if ($LASTEXITCODE -ne 0) { throw "SQLite integrity check failed. STOP." }
```

The opt-in `scripts/sqlite_snapshot.py` tool uses a **read-only source SQLite
connection** and the SQLite online backup API, checks `quick_check` and
`integrity_check` on the completed snapshot, then publishes a new file via
an atomic, non-overwriting hard link. It fails closed when source/target are
the same, the target already exists, the source is invalid, integrity fails
or the destination filesystem cannot support safe publication. It creates no
destination directories and does not import app modules or perform migration.
If your volume does not support hard links, use an operator-approved SQLite
backup process instead; do not weaken overwrite checks to work around this.

A successful snapshot proves **file integrity at backup time**, not that the
restore or application schema upgrade will succeed. Check permissions, disk
space and backup retention, and verify an off-host copy separately.

## Isolated rehearsal before promotion

After creating a verified backup:

1. Copy the verified snapshot to a disposable staging location **with a
   different absolute path**. Keep the original backup immutable.
2. In an isolated environment, set `DATABASE_PATH` to that staging copy.
   Disable schedulers, order/execution gateways, network side effects and
   credentials. Never let the staging process reach live trading.
3. Record before/after `PRAGMA integrity_check`, core table row counts,
   `intelligence_items` index names/definitions, primary keys, `stock_daily`
   history, and an isolated read-only BIST100 screening result. Investigate
   unexplained data changes or refusal on custom triggers/indexes/FKs.
4. Stop the rehearsal and retain logs. **Any failure or unexpected difference
   blocks production promotion.** Do not manually delete custom indexes or
   bypass fail-closed checks to make a migration pass.

### Automated disposable migration rehearsal (PowerShell)

From the repository root, after the snapshot above passes verification, run
the following **in a restricted non-production Python environment** with
execution gateways, schedulers, credentials and notifications disabled:

```powershell
python -m scripts.sqlite_migration_rehearsal --backup "$backup"
if ($LASTEXITCODE -ne 0) { throw "Isolated SQLite migration rehearsal FAILED. STOP." }
```

The rehearsal script creates its **own temporary SQLite clone** using the
read-only-source online backup API and passes only that temporary path to
`DatabaseManager`. It checks preexisting table counts, hashes the stable
historical OHLCV columns in `stock_daily` and preserved source/title/URL
columns of `intelligence_items`, and verifies post-migration integrity.
It deletes the staged copy at exit. It **never** opens the input backup
with a write connection. New migration metadata rows may be expected.

**A passing automated rehearsal is only one gate.** The operator must still
examine old/new schema and custom indexes/constraints, record an isolated
read-only BIST ranking, verify a separately restorable backup and obtain
explicit review. In particular the script does not compare every cell of
every table, check third-party provider availability, or certify production
rollout. A failed or refused migration never authorizes bypassing SQLite
safety checks.

## Manual rollback — only during an approved outage

Rollback is intentionally **not** automated by this tool.

1. Stop the web backend, workers and any other SQLite readers/writers;
   verify there are no open database connections. Record the exact failure.
2. Preserve the failed live database **and any associated `-wal`/`-shm`
   sidecars** together in a separately secured incident directory. Do not
   delete or reuse those sidecars and do not attach them to a restored file.
   With all connections closed, a controlled checkpoint may be appropriate;
   do not force one onto an already suspect database without expert review.
3. Re-verify the immutable pre-migration snapshot with `--verify-only`.
   Restore a **copy** of it to the original `DATABASE_PATH` only after the old
   database and sidecars are moved aside and the original target path is
   absent. Preserve ownership/ACLs. Never overwrite the only backup.
4. Before restarting the application, verify the restored file using
   `--verify-only`; compare key tables and stock history against recorded
   baselines. Keep the application stopped if there is a discrepancy.
5. Restart only after an operator validates the restored version, migrations
   are compatible with that version and execution/schedulers remain disabled
   pending explicit authorization. Preserve incident logs and hashes.

**Stop conditions:** missing/invalid backups, failed checks, unexpected row
count changes, SQLite lock/corruption, unexplained indexes/triggers/FKs,
provider/market inconsistencies or unavailable rollback authority.

## Evidence boundary

PR #8's isolated real-data test imported 100 BIST tickers and scored all
100, but that does not validate a live deployment. The six international
market probes each exercise one representative stock; they do not establish
whole-market coverage. All snapshots, rehearsals and approvals above remain
required before any production change.
