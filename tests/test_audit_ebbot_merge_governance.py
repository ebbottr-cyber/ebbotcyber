"""Offline contract checks for main merge governance preflight."""
import unittest
from scripts.audit_ebbot_merge_governance import inspect, matches_main

SHA = "f" * 40


def good():
    return (
        {"protected": True},
        {"number": 188, "state": "open", "draft": False,
         "base": {"ref": "main"}, "head": {"sha": SHA},
         "user": {"login": "owner"}},
        [{"user": {"login": "independent"}, "state": "APPROVED", "commit_id": SHA}],
        [{"target": "branch", "enforcement": "active",
          "conditions": {"ref_name": {"include": ["refs/heads/main"], "exclude": []}},
          "rules": [
              {"type": "pull_request", "parameters": {
                  "required_approving_review_count": 1, "dismiss_stale_reviews_on_push": True}},
              {"type": "required_status_checks", "parameters": {
                  "strict_required_status_checks_policy": True,
                  "required_status_checks": [{"context":
                      "EBBot required gate / all offline acceptance checks"}]}},
              {"type": "non_fast_forward"},
              {"type": "deletion"},
          ]}],
    )


class GovernanceTest(unittest.TestCase):
    def blocked(self, values, name):
        result = inspect(*values, SHA)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn(name, result["blockers"])
        self.assertFalse(result["release_authorized"])
        self.assertFalse(result["main_merged"])
        self.assertFalse(result["trading_authorized"])

    def test_valid_preflight_not_release(self):
        result = inspect(*good(), SHA)
        self.assertEqual(result["status"], "GOVERNANCE_PRECHECK_PASSED")
        self.assertFalse(result["release_authorized"])

    def test_main_unprotected(self):
        x = good(); x[0]["protected"] = False
        self.blocked(x, "MAIN_NOT_PROTECTED")

    def test_ruleset_absent(self):
        x = good(); x[3].clear()
        self.blocked(x, "ACTIVE_MAIN_RULESET_MISSING")

    def test_evaluate_ruleset(self):
        x = good(); x[3][0]["enforcement"] = "evaluate"
        self.blocked(x, "ACTIVE_MAIN_RULESET_MISSING")

    def test_ruleset_other_branch(self):
        x = good(); x[3][0]["conditions"]["ref_name"]["include"] = ["refs/heads/dev"]
        self.blocked(x, "ACTIVE_MAIN_RULESET_MISSING")

    def test_default_branch_selector(self):
        x = good(); x[3][0]["conditions"]["ref_name"]["include"] = ["~DEFAULT_BRANCH"]
        self.assertEqual(inspect(*x, SHA)["status"], "GOVERNANCE_PRECHECK_PASSED")

    def test_excluded_main(self):
        x = good(); x[3][0]["conditions"]["ref_name"]["exclude"] = ["refs/heads/main"]
        self.blocked(x, "ACTIVE_MAIN_RULESET_MISSING")

    def test_no_review_rule(self):
        x = good(); x[3][0]["rules"][0]["parameters"]["required_approving_review_count"] = 0
        self.blocked(x, "PULL_REQUEST_APPROVAL_RULE_MISSING")

    def test_no_stale_guard(self):
        x = good(); x[3][0]["rules"][0]["parameters"]["dismiss_stale_reviews_on_push"] = False
        self.blocked(x, "STALE_APPROVAL_GUARD_MISSING")

    def test_wrong_check(self):
        x = good(); x[3][0]["rules"][1]["parameters"]["required_status_checks"][0]["context"] = "wrong"
        self.blocked(x, "STRICT_REQUIRED_CHECK_MISSING")

    def test_non_strict_check(self):
        x = good(); x[3][0]["rules"][1]["parameters"]["strict_required_status_checks_policy"] = False
        self.blocked(x, "STRICT_REQUIRED_CHECK_MISSING")

    def test_force_push_not_prohibited(self):
        x = good(); x[3][0]["rules"].pop(2)
        self.blocked(x, "FORCE_PUSH_PROTECTION_MISSING")

    def test_deletion_not_prohibited(self):
        x = good(); x[3][0]["rules"].pop()
        self.blocked(x, "DELETE_PROTECTION_MISSING")

    def test_unlimited_bypass(self):
        x = good(); x[3][0]["bypass_actors"] = [{"bypass_mode": "always"}]
        self.blocked(x, "UNRESTRICTED_BYPASS")

    def test_draft_not_ready(self):
        x = good(); x[1]["draft"] = True
        self.blocked(x, "PR_NOT_READY")

    def test_head_drift(self):
        x = good(); x[1]["head"]["sha"] = "a" * 40
        self.blocked(x, "PR_HEAD_DRIFT")

    def test_author_self_review(self):
        x = good(); x[2][0]["user"]["login"] = "owner"
        self.blocked(x, "INDEPENDENT_CURRENT_SHA_APPROVAL_MISSING")

    def test_old_approval_not_counted(self):
        x = good(); x[2][0]["commit_id"] = "a" * 40
        self.blocked(x, "INDEPENDENT_CURRENT_SHA_APPROVAL_MISSING")

    def test_changes_requested_reverses_approval(self):
        x = good(); x[2].append({"user": {"login": "independent"},
                                 "state": "CHANGES_REQUESTED", "commit_id": SHA})
        self.blocked(x, "INDEPENDENT_CURRENT_SHA_APPROVAL_MISSING")

    def test_comment_after_approval_does_not_override(self):
        x = good(); x[2].append({"user": {"login": "independent"},
                                 "state": "COMMENTED", "commit_id": SHA})
        self.assertEqual(inspect(*x, SHA)["status"], "GOVERNANCE_PRECHECK_PASSED")

    def test_main_ref_pattern(self):
        self.assertTrue(matches_main({"ref_name": {"include": ["refs/heads/m*"]}}))
        self.assertFalse(matches_main({"ref_name": {"include": []}}))


if __name__ == "__main__":
    unittest.main()
