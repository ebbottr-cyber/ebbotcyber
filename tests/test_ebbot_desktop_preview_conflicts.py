"""Synthetic Git fixture tests for the isolated conflict-preview index.

No real EBBot branch refs are changed; test ref names are local/temp only.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "ebbot_desktop_preview_conflict_resolution.py"
spec = importlib.util.spec_from_file_location("ebbot_preview", SCRIPT)
preview_module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(preview_module)


class EBBotPreviewResolutionTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="ebbot-preview-synthetic-")
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name)
        self.git("init", "-q")
        self.git("config", "user.name", "EBBot synthetic test")
        self.git("config", "user.email", "test@example.invalid")
        (self.repo / "shared.txt").write_text("original\n", encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-qm", "baseline")
        self.git("branch", "baseline")
        self.git("checkout", "-qb", "candidate")
        (self.repo / "shared.txt").write_text("candidate version\n", encoding="utf-8")
        (self.repo / "candidate_only.txt").write_text("candidate\n", encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-qm", "candidate changes")
        self.candidate_sha = self.git("rev-parse", "HEAD")
        self.git("checkout", "baseline")
        (self.repo / "shared.txt").write_text("main version\n", encoding="utf-8")
        (self.repo / "main_only.txt").write_text("main\n", encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-qm", "main changes")
        self.main_sha = self.git("rev-parse", "HEAD")
        outcome = self.git_raw("merge-tree", "--write-tree", "--messages",
                               self.main_sha, self.candidate_sha)
        self.assertEqual(outcome.returncode, 1)
        self.tree_sha = outcome.stdout.splitlines()[0].strip()

    def git_raw(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args],
                              capture_output=True, text=True, check=False)

    def git(self, *args):
        p = self.git_raw(*args)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout.strip()

    def report(self):
        return {
            "schema_version": 1,
            "status": "REVIEW_REQUIRED_CONFLICTS",
            "release_status": "BLOCKED",
            "base_sha": self.main_sha,
            "candidate_sha": self.candidate_sha,
            "merge_tree_sha": self.tree_sha,
            "conflict_messages": ["CONFLICT (content): Merge conflict in shared.txt"],
            "conflict_message_count": 1,
        }

    def test_preview_resolves_only_pinned_conflict_and_keeps_main_files(self):
        before = (self.git("rev-parse", "baseline"),
                  self.git("rev-parse", "candidate"),
                  self.git("symbolic-ref", "--short", "HEAD"))
        with (patch.object(preview_module, "EXPECTED_MAIN", self.main_sha),
              patch.object(preview_module, "EXPECTED_STACK", self.candidate_sha),
              patch.object(preview_module, "REVIEW_ONLY_REPLACEMENTS", ("shared.txt",))):
            data = preview_module.preview(self.repo, self.report())
        tree = data["synthetic_tree_sha"]
        self.assertEqual(self.git("show", tree + ":shared.txt"), "candidate version")
        self.assertEqual(self.git("show", tree + ":main_only.txt"), "main")
        self.assertEqual(self.git("show", tree + ":candidate_only.txt"), "candidate")
        self.assertEqual(data["release_status"], "BLOCKED")
        self.assertFalse(data["merges_performed"])
        self.assertFalse(data["human_approval_to_merge"])
        self.assertEqual(before, (self.git("rev-parse", "baseline"),
                                  self.git("rev-parse", "candidate"),
                                  self.git("symbolic-ref", "--short", "HEAD")))

    def test_new_main_sha_fails_closed_before_writing_any_resolution(self):
        with patch.object(preview_module, "EXPECTED_STACK", self.candidate_sha):
            with self.assertRaisesRegex(ValueError, "Unreviewed main"):
                preview_module.preview(self.repo, self.report())

    def test_unreviewed_fifth_conflict_must_fail(self):
        data = self.report()
        data["conflict_messages"].append("CONFLICT (content): Merge conflict in unknown.txt")
        data["conflict_message_count"] = 2
        with (patch.object(preview_module, "EXPECTED_MAIN", self.main_sha),
              patch.object(preview_module, "EXPECTED_STACK", self.candidate_sha),
              patch.object(preview_module, "REVIEW_ONLY_REPLACEMENTS", ("shared.txt",))):
            with self.assertRaisesRegex(ValueError, "Conflict list changed"):
                preview_module.preview(self.repo, data)


if __name__ == "__main__":
    unittest.main()
