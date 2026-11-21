"""Pure offline regressions for conflict inventory; never mutates repository refs."""
import unittest
from scripts.audit_ebbot_conflict_test_preservation import (
    CONFLICT_TEST_PATHS,
    PROTECTED_NON_TEST_PATHS,
    difference,
    testcase_names,
)


class ConflictTestPreservationTest(unittest.TestCase):
    def test_extracts_test_titles_and_skips(self):
        text = """
it('keeps this case', () => {});
it.skip("historical skip", () => {});
test('explicit Turkish', async () => {});
"""
        self.assertEqual(testcase_names(text), {
            "keeps this case", "historical skip", "explicit Turkish",
        })
        result = difference(text, text.replace("historical skip", "changed skip"))
        self.assertEqual(result["react_skip_literals"], 1)
        self.assertEqual(result["windows_skip_literals"], 1)
        self.assertEqual(result["react_only_test_titles"], ["historical skip"])
        self.assertEqual(result["windows_only_test_titles"], ["changed skip"])

    def test_detects_two_sided_test_additions(self):
        react = "it('React-only FX snapshot', () => {});\nit('shared', () => {});"
        windows = "it('Windows-only TRY provider outage', () => {});\nit('shared', () => {});"
        check = difference(react, windows)
        self.assertEqual(check["react_only_test_titles"], ["React-only FX snapshot"])
        self.assertEqual(check["windows_only_test_titles"], ["Windows-only TRY provider outage"])
        self.assertTrue(check["requires_human_semantic_review"])

    def test_same_titles_still_require_code_review(self):
        check = difference("it('same', () => 1);", "it('same', () => 2);")
        self.assertFalse(check["react_only_test_titles"])
        self.assertFalse(check["windows_only_test_titles"])
        self.assertTrue(check["requires_human_semantic_review"])

    def test_policy_inventory_coverage(self):
        self.assertEqual(len(CONFLICT_TEST_PATHS), 16)
        self.assertEqual(len(set(CONFLICT_TEST_PATHS)), 16)
        self.assertEqual(len(PROTECTED_NON_TEST_PATHS), 2)
        self.assertTrue(all(path.endswith(".test.tsx") for path in CONFLICT_TEST_PATHS))
        self.assertIn("scripts/probe_ebbot_packaged_health.py", PROTECTED_NON_TEST_PATHS)


if __name__ == "__main__":
    unittest.main()
