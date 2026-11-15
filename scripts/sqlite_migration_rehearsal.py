"""Rehearse application SQLite startup/migrations on a disposable database copy.

This command *never* starts the app against the input file. It uses the
read-only-source online backup helper to create a temporary, verified clone,
then invokes DatabaseManager only with the clone's explicit SQLite URL.
It cannot approve production migration or validate active trading.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile

from scripts.sqlite_snapshot import create_snapshot, verify_snapshot, _open_readonly

# Only columns that migrations must never rewrite. canonical_id and scope_value
# are intentionally excluded: legacy backfills may populate them.
_CRITICAL = {
    "stock_daily": ("id", "code", "date", "open", "high", "low", "close",
                    "volume", "data_source"),
    "intelligence_items": ("id", "source_id", "title", "url", "raw_payload"),
}
# Recording a schema-version row during a successful migration is expected.
_ALLOWED_COUNT_CHANGE = {"schema_migrations"}


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _read_baseline(path: Path) -> dict[str, object]:
    """Count existing user tables and fingerprint immutable trading history."""
    with _open_readonly(path) as db:
        names = [
            name for (name,) in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        counts: dict[str, int] = {}
        digests: dict[str, dict[str, object]] = {}
        for name in names:
            counts[name] = int(db.execute(
                f"SELECT COUNT(*) FROM {_quote_identifier(name)}"
            ).fetchone()[0])
            if name not in _CRITICAL:
                continue
            existing = {
                row[1] for row in db.execute(
                    f"PRAGMA table_info({_quote_identifier(name)})"
                )
            }
            # A real application table must have a stable primary key.
            if "id" not in existing:
                raise RuntimeError(f"Critical table {name!r} has no id column")
            columns = [col for col in _CRITICAL[name] if col in existing]
            if name == "stock_daily" and not {"code", "date", "close"}.issubset(existing):
                raise RuntimeError("stock_daily lacks essential price columns")
            if name == "intelligence_items" and not {"url", "title"}.issubset(existing):
                raise RuntimeError("intelligence_items lacks essential columns")
            select = ", ".join(_quote_identifier(c) for c in columns)
            digest = hashlib.sha256()
            for row in db.execute(
                f"SELECT {select} FROM {_quote_identifier(name)} ORDER BY id"
            ):
                # Length-prefix each serialized tuple to avoid concatenation ambiguity.
                payload = repr(tuple(row)).encode("utf-8", errors="surrogatepass")
                digest.update(len(payload).to_bytes(8, "big"))
                digest.update(payload)
            digests[name] = {"columns": columns, "sha256": digest.hexdigest()}
        return {"counts": counts, "critical_digests": digests}


def _migrate_isolated(path: Path) -> None:
    """Run the real app's database bootstrap strictly against a staging path."""
    from src.config import Config
    from src.storage import DatabaseManager

    Config.reset_instance()
    DatabaseManager.reset_instance()
    try:
        absolute = path.resolve(strict=True)
        # SQLite URL with four leading slashes for absolute POSIX paths.
        DatabaseManager(db_url=f"sqlite:///{absolute.as_posix()}")
    finally:
        DatabaseManager.reset_instance()
        Config.reset_instance()


def rehearse(source: Path) -> dict[str, object]:
    """Make a verified clone and enforce unchanged rows/critical cell values."""
    source = Path(source).expanduser().resolve(strict=True)
    verified_source = verify_snapshot(source)
    with tempfile.TemporaryDirectory(prefix="ebbot-sqlite-rehearsal-") as directory:
        stage = Path(directory) / "rehearsal.sqlite"
        if stage.resolve() == source:
            raise RuntimeError("Refusing to rehearse against the source database")
        create_snapshot(source, stage)
        before = _read_baseline(stage)
        _migrate_isolated(stage)
        verify_snapshot(stage)
        after = _read_baseline(stage)

        old_counts = before["counts"]
        new_counts = after["counts"]
        for name, old_count in old_counts.items():
            if name in _ALLOWED_COUNT_CHANGE:
                continue
            new_count = new_counts.get(name)
            if new_count != old_count:
                raise RuntimeError(
                    f"Migration changed table {name!r} row count: "
                    f"{old_count} -> {new_count}"
                )
        for name, digest in before["critical_digests"].items():
            if after["critical_digests"].get(name) != digest:
                raise RuntimeError(
                    f"Migration changed critical {name!r} historical values"
                )

        return {
            "status": "isolated_rehearsal_passed",
            "input_verified": verified_source["integrity"],
            "post_migration_integrity": "ok",
            "preexisting_tables_preserved": sorted(
                name for name in old_counts if name not in _ALLOWED_COUNT_CHANGE
            ),
            "critical_tables_fingerprinted": sorted(before["critical_digests"]),
            "new_tables": sorted(set(new_counts) - set(old_counts)),
            "disclaimer": "Synthetic/isolated rehearsal only; no production approval.",
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup", required=True, type=Path,
                        help="Verified SQLite snapshot; never migrated in place")
    args = parser.parse_args(argv)
    try:
        result = rehearse(args.backup)
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
        print(f"Isolated migration rehearsal BLOCKED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
