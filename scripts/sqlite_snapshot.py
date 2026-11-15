"""Opt-in, read-only-source SQLite snapshot and integrity verifier.

The source is opened with SQLite URI mode=ro and snapshotted using the
online backup API. A new destination is published only after verification.
This tool never starts the application or runs schema migrations.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile


def _open_readonly(path: Path) -> sqlite3.Connection:
    resolved = path.expanduser().resolve(strict=True)
    if not resolved.is_file():
        raise ValueError(f"Not a regular SQLite file: {resolved}")
    return sqlite3.connect(resolved.as_uri() + "?mode=ro", uri=True, timeout=30)


def verify_snapshot(path: Path) -> dict[str, object]:
    """Read-only integrity verification; never repairs or migrates a file."""
    path = Path(path)
    with _open_readonly(path) as db:
        quick = [str(row[0]) for row in db.execute("PRAGMA quick_check")]
        if quick != ["ok"]:
            raise RuntimeError(f"SQLite quick_check failed: {quick[:3]}")
        integrity = [str(row[0]) for row in db.execute("PRAGMA integrity_check")]
        if integrity != ["ok"]:
            raise RuntimeError(f"SQLite integrity_check failed: {integrity[:3]}")
        tables = int(db.execute(
            "SELECT COUNT(*) FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchone()[0])
        if not tables:
            raise RuntimeError("SQLite backup has no application tables")
    return {"path": str(path.resolve()), "integrity": "ok", "tables": tables,
            "bytes": path.stat().st_size}


def create_snapshot(source: Path, output: Path) -> dict[str, object]:
    """Online SQLite backup; never overwrites an existing destination."""
    source, output = Path(source).expanduser(), Path(output).expanduser()
    source_resolved = source.resolve(strict=True)
    output_resolved = output.resolve(strict=False)
    if source_resolved == output_resolved:
        raise ValueError("Source and output must be different files")
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Refusing to overwrite existing backup: {output}")
    if not output.parent.is_dir():
        raise ValueError(f"Backup output directory does not exist: {output.parent}")

    # Create a private temporary file in the destination's own filesystem.
    fd, staged = tempfile.mkstemp(prefix=".sqlite-snapshot-", suffix=".tmp",
                                dir=str(output.parent))
    os.close(fd)
    try:
        src = _open_readonly(source_resolved)
        try:
            target = sqlite3.connect(staged, timeout=30)
            try:
                src.backup(target, pages=256, sleep=0.1)
            finally:
                target.close()
        finally:
            src.close()

        # Verify a completed, closed snapshot before making it visible.
        report = verify_snapshot(Path(staged))
        with open(staged, "rb") as file:
            os.fsync(file.fileno())
        # Hard-link publish is atomic and fails rather than overwriting an
        # output created by a concurrent operator/process. Same dir/volume.
        os.link(staged, output)
        return {**report, "path": str(output.resolve()), "source": str(source_resolved)}
    finally:
        if os.path.exists(staged):
            os.unlink(staged)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--source", type=Path, help="Existing SQLite database to back up")
    modes.add_argument("--verify-only", type=Path, help="Existing snapshot to verify")
    parser.add_argument("--output", type=Path, help="New backup path (must not exist)")
    args = parser.parse_args(argv)
    if args.source and not args.output:
        parser.error("--source requires --output")
    if args.verify_only and args.output:
        parser.error("--verify-only cannot be combined with --output")
    try:
        report = (verify_snapshot(args.verify_only) if args.verify_only
                  else create_snapshot(args.source, args.output))
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
        print(f"SQLite snapshot failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
