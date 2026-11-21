#!/usr/bin/env python3
"""Offline synthetic SQLite test against the actual frozen PyInstaller backend.

Only runs the early one-shot --ebbot-desktop-sqlite-snapshot handler.
It does NOT launch the app/server, execute market jobs, or touch user files.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile


def smoke(executable: Path) -> dict:
    if not executable.is_file():
        raise FileNotFoundError("Frozen backend binary not found")
    with tempfile.TemporaryDirectory(prefix="ebbot-frozen-sqlite-ci-") as root:
        folder = Path(root)
        source = folder / "stock_analysis.db"
        target = folder / "stock_analysis.snapshot.db"
        with closing(sqlite3.connect(source)) as writer:
            if writer.execute("PRAGMA journal_mode=WAL").fetchone()[0] != "wal":
                raise AssertionError("Synthetic source could not use WAL")
            writer.execute("CREATE TABLE integrity_probe (item TEXT NOT NULL)")
            writer.execute("INSERT INTO integrity_probe VALUES ('committed')")
            writer.commit()
        live_writer = sqlite3.connect(source)
        try:
            live_writer.execute("BEGIN IMMEDIATE")
            live_writer.execute("INSERT INTO integrity_probe VALUES ('uncommitted')")
            result = subprocess.run(
                [str(executable.resolve()), "--ebbot-desktop-sqlite-snapshot",
                 "--source", str(source), "--destination", str(target)],
                cwd=folder, capture_output=True, text=True, check=False, timeout=45,
            )
            if result.returncode:
                raise AssertionError("Frozen offline snapshot command returned a failure")
            report = json.loads(result.stdout)
            if report.get("status") != "PASSED" or report.get("release_status") != "BLOCKED":
                raise AssertionError("Frozen snapshot did not return blocked offline success")
            if report.get("method") != "sqlite3.Connection.backup":
                raise AssertionError("Expected SQLite's transactional backup API")
            with closing(sqlite3.connect(target)) as checked:
                if checked.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                    raise AssertionError("Frozen SQLite snapshot has failed integrity_check")
                if checked.execute("SELECT COUNT(*) FROM integrity_probe").fetchone() != (1,):
                    raise AssertionError("Snapshot must exclude uncommitted WAL changes")
            if hashlib.sha256(target.read_bytes()).hexdigest() != report.get("sha256"):
                raise AssertionError("Snapshot hash mismatch")
            if source.stat().st_size <= 0 or target.stat().st_size <= 0:
                raise AssertionError("Empty source or target SQLite snapshot")
            return {"frozen_sqlite_snapshot": "PASSED", "wal_consistency": "PASSED",
                    "release_status": "BLOCKED", "user_data_touched": False}
        finally:
            live_writer.rollback()
            live_writer.close()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--backend-exe", type=Path, required=True)
    args = p.parse_args()
    try:
        result = smoke(args.backend_exe)
    except (OSError, ValueError, AssertionError, sqlite3.DatabaseError, subprocess.TimeoutExpired):
        print(json.dumps({"frozen_sqlite_snapshot": "FAILED", "release_status": "BLOCKED"}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
