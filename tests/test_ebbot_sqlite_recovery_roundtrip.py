"""End-to-end *synthetic* SQLite WAL/rollback rehearsal across Python and Node.

No production DB, application instance, broker, scheduler or installer is used.
The test creates its own tiny committed/uncommitted SQLite transactions inside
tempfile.TemporaryDirectory and passes only their bytes to a bounded offline
Electron rehearsal helper.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest

from scripts.ebbot_sqlite_snapshot import snapshot_sqlite_database

ROOT = Path(__file__).resolve().parents[1]
REHEARSAL_MODULE = ROOT / "apps" / "dsa-desktop" / "sqliteRollbackRehearsal.js"
DB = "stock_analysis.db"

NODE_DRIVER = r"""
const fs = require('node:fs');
const helper = require(process.argv[3]);
const mode = process.argv[1], root = process.argv[2];
if (mode === 'create') {
  const input = JSON.parse(fs.readFileSync(0, 'utf8'));
  const bytes = name => Buffer.from(input[name], 'base64');
  console.log(JSON.stringify({root: helper.createSqliteBundleRehearsal({
    existingDb: bytes('originalDb'),
    existingWal: bytes('originalWal'),
    existingShm: bytes('originalShm'),
    candidateDb: bytes('snapshotDb'),
  })}));
} else if (mode === 'crash') {
  const path = require('node:path');
  const originalRename = fs.renameSync;
  fs.renameSync = (from, to) => {
    const result = originalRename(from, to);
    if (from === path.join(root, 'active') && to === path.join(root, 'previous'))
      process.exit(71);
    return result;
  };
  helper.rehearseSqlitePromotion(root);
} else {
  const handler = {
    promote: helper.rehearseSqlitePromotion,
    rollback: helper.rollbackCompletedSqlitePromotion,
    recover: helper.recoverInterruptedSqlitePromotion,
  }[mode];
  if (!handler) throw new Error('Invalid test mode');
  console.log(JSON.stringify(handler(root)));
}
"""


class SQLiteRealWALRecoveryRehearsalTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="ebbot-wal-roundtrip-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.database = self.root / DB
        self.snapshot = self.root / "snapshot.db"

        writer = sqlite3.connect(self.database)
        try:
            self.assertEqual(writer.execute("PRAGMA journal_mode=WAL").fetchone(), ("wal",))
            writer.execute("CREATE TABLE observations (name TEXT NOT NULL)")
            writer.execute("INSERT INTO observations VALUES ('before-wal')")
            writer.commit()
            writer.execute("INSERT INTO observations VALUES ('committed-in-wal')")
            writer.commit()
            writer.execute("BEGIN IMMEDIATE")
            writer.execute("INSERT INTO observations VALUES ('uncommitted-do-not-restore')")

            # The original DB/WAL/SHM are captured while SQLite keeps the
            # WAL alive; this is a controlled fixture with NO concurrent write.
            original = {}
            for name, suffix in (("originalDb", ""), ("originalWal", "-wal"),
                                 ("originalShm", "-shm")):
                location = Path(str(self.database) + suffix)
                self.assertTrue(location.is_file(), name + " missing")
                original[name] = base64.b64encode(location.read_bytes()).decode("ascii")

            report = snapshot_sqlite_database(self.database, self.snapshot)
            self.assertEqual(report["status"], "PASSED")
            self.assertEqual(report["release_status"], "BLOCKED")
            original["snapshotDb"] = base64.b64encode(self.snapshot.read_bytes()).decode("ascii")
            self.payload = json.dumps(original)
        finally:
            writer.rollback()
            writer.close()

        # This module accepts only tiny synthetic Buffers; deliberately keep
        # this test well below its 64 KiB per-file bound.
        for encoded in json.loads(self.payload).values():
            self.assertLessEqual(len(base64.b64decode(encoded)), 65536)
        created = self._node("create", "", stdin=self.payload)
        self.workspace = Path(json.loads(created.stdout)["root"])
        self.addCleanup(self._cleanup_workspace)

    def _cleanup_workspace(self):
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def _node(self, mode: str, folder: str | Path, *, stdin: str = "",
              expected_exit: int = 0) -> subprocess.CompletedProcess[str]:
        run = subprocess.run(
            ["node", "-e", NODE_DRIVER, mode, str(folder), str(REHEARSAL_MODULE)],
            cwd=ROOT, input=stdin, capture_output=True, text=True, check=False,
            timeout=20,
        )
        self.assertEqual(run.returncode, expected_exit,
                         f"Node isolated {mode} failed: {run.stderr[:500]}")
        return run

    def _rows(self, directory: Path) -> list[str]:
        database = directory / DB
        connection = sqlite3.connect(database)
        try:
            self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone(), ("ok",))
            return [row[0] for row in connection.execute(
                "SELECT name FROM observations ORDER BY rowid")]
        finally:
            connection.close()

    def _assert_committed_only(self, folder: Path):
        self.assertEqual(self._rows(folder), ["before-wal", "committed-in-wal"])
        self.assertNotIn("uncommitted-do-not-restore", self._rows(folder))

    def test_real_sqlite_wal_snapshot_and_full_old_bundle_rollback(self):
        self.assertEqual(json.loads(self._node("promote", self.workspace).stdout)["releaseStatus"], "BLOCKED")
        self._assert_committed_only(self.workspace / "active")
        self.assertEqual(sorted(p.name for p in (self.workspace / "active").iterdir()), [DB])
        self.assertTrue((self.workspace / "previous" / (DB + "-wal")).exists())
        self.assertTrue((self.workspace / "previous" / (DB + "-shm")).exists())
        self.assertEqual(json.loads(self._node("rollback", self.workspace).stdout)["releaseStatus"], "BLOCKED")
        self._assert_committed_only(self.workspace / "active")
        self._assert_committed_only(self.workspace / "candidate-quarantine")

    def test_real_sqlite_wal_survives_abrupt_node_exit_before_promotion(self):
        self._node("crash", self.workspace, expected_exit=71)
        self.assertFalse((self.workspace / "active").exists())
        self.assertTrue((self.workspace / "previous" / (DB + "-wal")).exists())
        self.assertTrue((self.workspace / "previous" / (DB + "-shm")).exists())
        recovered = json.loads(self._node("recover", self.workspace).stdout)
        self.assertEqual(recovered["status"], "ORIGINAL_RECOVERED")
        self.assertEqual(recovered["releaseStatus"], "BLOCKED")
        self._assert_committed_only(self.workspace / "active")
        self._assert_committed_only(self.workspace / "candidate")


if __name__ == "__main__":
    unittest.main()
