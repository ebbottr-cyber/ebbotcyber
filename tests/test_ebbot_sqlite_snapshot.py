"""Regression contracts for the isolated SQLite online-backup CLI.

All data is synthetic. No backend service, network, scheduled scans or trades.
"""
from __future__ import annotations

import json
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts.ebbot_sqlite_snapshot import snapshot_sqlite_database

ROOT = Path(__file__).resolve().parents[1]


class SQLiteOnlineSnapshotTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)
        self.source = self.folder / "stock_analysis.db"
        self.destination = self.folder / "backup" / "stock_analysis.db"
        self.destination.parent.mkdir()
        with closing(sqlite3.connect(self.source)) as database:
            database.execute("CREATE TABLE trades (id INTEGER PRIMARY KEY, label TEXT NOT NULL)")
            database.execute("INSERT INTO trades(label) VALUES (?)", ("committed-only",))
            database.commit()

    def _count(self, path):
        with closing(sqlite3.connect(path)) as database:
            return database.execute("SELECT COUNT(*) FROM trades").fetchone()[0]

    def test_wal_uncommitted_transaction_not_in_snapshot(self):
        with closing(sqlite3.connect(self.source)) as writer:
            self.assertEqual(writer.execute("PRAGMA journal_mode=WAL").fetchone()[0], "wal")
            writer.execute("INSERT INTO trades(label) VALUES (?)", ("committed-before-snapshot",))
            writer.commit()
        writer = sqlite3.connect(self.source, timeout=2)
        try:
            writer.execute("BEGIN IMMEDIATE")
            writer.execute("INSERT INTO trades(label) VALUES (?)", ("uncommitted",))
            result = snapshot_sqlite_database(self.source, self.destination)
            self.assertEqual(result["status"], "PASSED")
            self.assertEqual(result["method"], "sqlite3.Connection.backup")
            self.assertEqual(result["integrity_check"], "ok")
            self.assertEqual(result["release_status"], "BLOCKED")
            self.assertFalse(result["enables_updates"])
            self.assertFalse(result["starts_backend"])
            self.assertEqual(self._count(self.destination), 2)
            writer.commit()
            self.assertEqual(self._count(self.source), 3)
            self.assertEqual(self._count(self.destination), 2)
            with closing(sqlite3.connect(self.destination)) as snapshot:
                self.assertEqual(snapshot.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                self.assertEqual(snapshot.execute("PRAGMA journal_mode").fetchone()[0], "delete")
        finally:
            writer.close()
        self.assertFalse(Path(str(self.destination) + "-wal").exists())
        self.assertFalse(Path(str(self.destination) + "-shm").exists())
        self.assertEqual(sorted(p.name for p in self.destination.parent.iterdir()), ["stock_analysis.db"])

    def test_refuses_overwrite_existing_snapshot_without_modifying_it(self):
        self.destination.write_bytes(b"existing-recovery-copy")
        with self.assertRaises(FileExistsError):
            snapshot_sqlite_database(self.source, self.destination)
        self.assertEqual(self.destination.read_bytes(), b"existing-recovery-copy")

    def test_corrupt_database_fails_closed_and_removes_temp(self):
        self.source.write_bytes(b"not a SQLite database")
        with self.assertRaises(sqlite3.DatabaseError):
            snapshot_sqlite_database(self.source, self.destination)
        self.assertFalse(self.destination.exists())
        self.assertEqual(list(self.destination.parent.iterdir()), [])

    def test_publish_failure_keeps_target_absent_and_removes_temp(self):
        with patch("scripts.ebbot_sqlite_snapshot.os.link", side_effect=OSError("hardlink blocked")):
            with self.assertRaises(OSError):
                snapshot_sqlite_database(self.source, self.destination)
        self.assertFalse(self.destination.exists())
        self.assertEqual(list(self.destination.parent.iterdir()), [])

    def test_symlinked_source_rejected(self):
        source_link = self.folder / "linked.db"
        try:
            source_link.symlink_to(self.source)
        except (OSError, NotImplementedError):
            self.skipTest("Symlink creation unavailable on this runner")
        with self.assertRaises(ValueError):
            snapshot_sqlite_database(source_link, self.destination)
        self.assertFalse(self.destination.exists())

    def test_source_and_destination_must_differ_and_parent_must_exist(self):
        with self.assertRaises(FileExistsError):
            snapshot_sqlite_database(self.source, self.source)
        with self.assertRaises(ValueError):
            snapshot_sqlite_database(self.source, self.folder / "absent" / "stock_analysis.db")

    def test_main_py_offline_dispatch_skips_normal_runtime(self):
        env = dict(os.environ)
        env.update({
            "MEME_COIN_DISCOVERY_ENABLED": "false",
            "SCHEDULE_ENABLED": "false",
            "RUNTIME_SCHEDULER_FORCE_ENABLED": "false",
            "DSA_PACKAGED_IMPORT_PROBE": "",
        })
        run = subprocess.run([
            sys.executable, str(ROOT / "main.py"), "--ebbot-desktop-sqlite-snapshot",
            "--source", str(self.source), "--destination", str(self.destination),
        ], cwd=ROOT, env=env, capture_output=True, text=True, timeout=20, check=False)
        self.assertEqual(run.returncode, 0, run.stderr)
        info = json.loads(run.stdout)
        self.assertEqual(info["status"], "PASSED")
        self.assertEqual(info["release_status"], "BLOCKED")
        self.assertEqual(self._count(self.destination), 1)
        self.assertNotIn(str(self.source), run.stdout)
        self.assertNotIn(str(self.destination), run.stdout)

    def test_main_py_offline_dispatch_returns_nonzero_on_bad_sqlite(self):
        self.source.write_bytes(b"broken-db")
        run = subprocess.run([
            sys.executable, str(ROOT / "main.py"), "--ebbot-desktop-sqlite-snapshot",
            "--source", str(self.source), "--destination", str(self.destination),
        ], cwd=ROOT, capture_output=True, text=True, timeout=20, check=False)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("BLOCKED", run.stderr)
        self.assertFalse(self.destination.exists())
        self.assertNotIn(str(self.source), run.stderr)


if __name__ == "__main__":
    unittest.main()
