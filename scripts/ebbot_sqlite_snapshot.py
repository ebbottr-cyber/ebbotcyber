#!/usr/bin/env python3
"""Offline SQLite snapshot using SQLite's transactional connection.backup API.

This is an explicit, isolated CLI for Windows desktop backup research. It does
not start EBBot services, install applications, connect to a broker, or enable
updates. No production data or secrets are bundled or uploaded.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import time


def snapshot_sqlite_database(source: Path, destination: Path, *, timeout_seconds: float = 30.0) -> dict:
    """Produce a consistent, standalone SQLite DB snapshot and publish it once.

    The source is opened read-only, SQLite handles WAL-aware page copying, and
    a private same-directory temporary DB is promoted only after integrity_check.
    Existing destination files are never overwritten, including symlinks.
    """
    source = Path(source)
    destination = Path(destination)
    if source.is_symlink() or not source.is_file():
        raise ValueError("SQLite source must be an existing regular non-symlink file")
    if destination.is_symlink() or destination.exists():
        raise FileExistsError("Snapshot destination must not already exist")
    if not destination.parent.is_dir() or destination.parent.is_symlink():
        raise ValueError("Snapshot destination parent must be an existing regular directory")
    if source.resolve() == destination.resolve(strict=False):
        raise ValueError("Snapshot source and destination must differ")
    if timeout_seconds <= 0 or timeout_seconds > 300:
        raise ValueError("Invalid SQLite backup timeout")

    tmp_path: Path | None = None
    deadline = time.monotonic() + timeout_seconds
    try:
        fd, temp_filename = tempfile.mkstemp(
            prefix=".ebbot-sqlite-snapshot-",
            suffix=".db",
            dir=destination.parent,
        )
        os.close(fd)
        tmp_path = Path(temp_filename)

        def check_progress(_status: int, _remaining: int, _total: int) -> None:
            if time.monotonic() > deadline:
                raise TimeoutError("SQLite online snapshot exceeded deadline")

        source_uri = source.resolve().as_uri() + "?mode=ro"
        with closing(sqlite3.connect(source_uri, uri=True, timeout=2.0)) as source_db:
            source_db.execute("PRAGMA query_only=ON")
            with closing(sqlite3.connect(tmp_path, timeout=2.0)) as target_db:
                source_db.backup(target_db, pages=128, progress=check_progress, sleep=0.05)
                if target_db.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                    raise ValueError("SQLite snapshot failed integrity_check")
                journal_mode = target_db.execute("PRAGMA journal_mode=DELETE").fetchone()[0]
                if journal_mode.lower() != "delete":
                    raise ValueError("Snapshot must use a standalone rollback journal")

        # Reopen the closed snapshot to validate the actual on-disk DB, not only
        # the in-memory destination connection used by SQLite.backup().
        with closing(sqlite3.connect(tmp_path.resolve().as_uri() + "?mode=ro", uri=True)) as verified:
            if verified.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                raise ValueError("Closed SQLite snapshot failed integrity_check")

        sha256 = hashlib.sha256()
        with tmp_path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                sha256.update(chunk)
        snapshot_size = tmp_path.stat().st_size
        if snapshot_size == 0:
            raise ValueError("Empty SQLite snapshot")

        # Atomic no-clobber publish on the same volume. On filesystems that do
        # not support hard links, fail closed rather than overwrite a target.
        os.link(tmp_path, destination)
        return {
            "status": "PASSED",
            "method": "sqlite3.Connection.backup",
            "integrity_check": "ok",
            "sha256": sha256.hexdigest(),
            "size_bytes": snapshot_size,
            "release_status": "BLOCKED",
            "starts_backend": False,
            "enables_updates": False,
        }
    finally:
        if tmp_path is not None:
            for candidate in (tmp_path, Path(str(tmp_path) + "-wal"),
                              Path(str(tmp_path) + "-shm"), Path(str(tmp_path) + "-journal")):
                try:
                    candidate.unlink(missing_ok=True)
                except OSError:
                    # The file cannot be mistaken for a complete published backup:
                    # its random temporary name never equals the destination.
                    pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = snapshot_sqlite_database(args.source, args.destination)
    except (OSError, ValueError, sqlite3.DatabaseError, TimeoutError) as exc:
        # Never print user source/destination paths or database contents.
        print("SQLite snapshot BLOCKED: " + type(exc).__name__, file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
