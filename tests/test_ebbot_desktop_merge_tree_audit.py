"""Only synthetic Git histories. The merge-tree audit must not modify refs."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audit_ebbot_desktop_merge_tree.py"
spec = importlib.util.spec_from_file_location("ebbot_merge_audit", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


class EBBotMergeTreeAuditTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="ebbot-safe-merge-tree-")
        self.addCleanup(temp.cleanup)
        self.repo = Path(temp.name)
        self.git("init", "-q")
        self.git("config", "user.name", "Synthetic EBBot Test")
        self.git("config", "user.email", "synthetic@example.test")
        (self.repo / "shared.txt").write_text("baseline\n", encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-qm", "synthetic baseline")
        self.git("branch", "main-test")
        self.git("checkout", "-qb", "desktop-test")

    def git(self, *args):
        output = subprocess.run(
            ["git", "-C", str(self.repo), *args],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(output.returncode, 0, output.stderr)
        return output.stdout.strip()

    def commit_text(self, filename, text):
        (self.repo / filename).write_text(text, encoding="utf-8")
        self.git("add", filename)
        self.git("commit", "-qm", "synthetic fixture change")

    def refs(self):
        return (self.git("rev-parse", "main-test"), self.git("rev-parse", "desktop-test"),
                self.git("symbolic-ref", "--short", "HEAD"))

    def test_non_overlapping_changes_are_clean_and_do_not_modify_branches(self):
        self.commit_text("desktop.txt", "desktop only\n")
        self.git("checkout", "main-test")
        self.commit_text("main.txt", "main only\n")
        before = self.refs()
        result = module.audit(self.repo, "main-test", "desktop-test")
        self.assertEqual(result["status"], "CLEAN_DRY_RUN")
        self.assertEqual(result["exact_overlap_count"], 0)
        self.assertEqual(result["release_status"], "BLOCKED")
        self.assertRegex(result["merge_tree_sha"], r"^[a-f0-9]{40,64}$")
        self.assertFalse(result["merges_performed"])
        self.assertFalse(result["branch_or_refs_modified"])
        self.assertEqual(self.refs(), before)

    def test_same_line_conflicts_fail_closed_without_modifying_branches(self):
        self.commit_text("shared.txt", "desktop replacement\n")
        self.git("checkout", "main-test")
        self.commit_text("shared.txt", "main replacement\n")
        before = self.refs()
        result = module.audit(self.repo, "main-test", "desktop-test")
        self.assertEqual(result["status"], "REVIEW_REQUIRED_CONFLICTS")
        self.assertEqual(result["exact_overlap_files"], ["shared.txt"])
        self.assertGreater(result["conflict_message_count"], 0)
        self.assertIn("CONFLICT", "\n".join(result["conflict_messages"]))
        self.assertEqual(result["release_status"], "BLOCKED")
        self.assertEqual(self.refs(), before)

    def test_same_filename_different_lines_may_be_clean_but_overlaps_are_reported(self):
        (self.repo / "shared.txt").write_text("first\nsecond\nthird\n", encoding="utf-8")
        self.git("add", "shared.txt")
        self.git("commit", "-qm", "rebase synthetic base")
        self.git("branch", "-f", "main-test", "HEAD")
        self.commit_text("shared.txt", "first modified\nsecond\nthird\n")
        self.git("checkout", "main-test")
        self.commit_text("shared.txt", "first\nsecond\nthird modified\n")
        result = module.audit(self.repo, "main-test", "desktop-test")
        self.assertEqual(result["exact_overlap_count"], 1)
        self.assertEqual(result["exact_overlap_files"], ["shared.txt"])
        self.assertEqual(result["release_status"], "BLOCKED")

    def test_unsafe_refs_are_rejected_before_git_execution(self):
        for value in ("--output", "../main", "HEAD^{tree}", ""):
            with self.subTest(ref=value):
                with self.assertRaises(ValueError):
                    module.audit(self.repo, value, "desktop-test")


if __name__ == "__main__":
    unittest.main()
