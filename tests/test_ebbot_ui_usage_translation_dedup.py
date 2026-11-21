"""Fail-closed offline unit tests for semantic TR usage duplicate resolution."""
import unittest

from scripts.resolve_ebbot_ui_usage_translation_dup import (
    EXTRA_MAIN_LINES, REQUIRED_EXISTING, deduplicate,
)


class TurkishUsageDedupTest(unittest.TestCase):
    def example(self):
        zh = [
            "  'usage.eyebrow': '使用',",
            "  'usage.title': '令牌用量',",
            "  'usage.description': '模型用量',",
        ]
        en = [
            "  'usage.eyebrow': 'Usage',",
            "  'usage.title': 'Token usage',",
            "  'usage.description': 'Usage details',",
        ]
        return "\n".join(zh + en + list(REQUIRED_EXISTING) + list(EXTRA_MAIN_LINES)) + "\n"

    def test_exact_known_auto_merge_duplicates_only(self):
        before = self.example()
        after = deduplicate(before)
        self.assertEqual(len(before.splitlines())-len(after.splitlines()), 3)
        for line in REQUIRED_EXISTING:
            self.assertIn(line, after)
        for line in EXTRA_MAIN_LINES:
            self.assertNotIn(line, after)

    def test_refuses_source_without_duplicate(self):
        original = "\n".join([
            "  'usage.eyebrow': 'Usage',",
            "  'usage.title': 'Token usage',",
            "  'usage.description': 'Usage description',",
        ]) + "\n"
        with self.assertRaises(ValueError):
            deduplicate(original)

    def test_refuses_unknown_fourth_language_entry(self):
        original = self.example().replace(
            "  'usage.eyebrow': 'Kullanım',",
            "  'usage.eyebrow': 'Unexpected',",
        )
        with self.assertRaises(ValueError):
            deduplicate(original)

    def test_refuses_removing_candidate_turkish_values(self):
        original = self.example().replace(
            """  'usage.eyebrow': "KULLANIM",""",
            """  'usage.eyebrow': "OTHER",""",
        )
        with self.assertRaises(ValueError):
            deduplicate(original)


if __name__ == "__main__":
    unittest.main()
