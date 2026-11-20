"""Synthetic trust-policy tests. No signing keys, binaries, installer execution or network."""
from __future__ import annotations

import unittest
from datetime import datetime, timezone

from scripts.audit_ebbot_desktop_signing import TARGETS, audit


class EBBotSigningPolicyTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 20, tzinfo=timezone.utc)
        self.fingerprint = "A" * 40
        self.policy = {
            "schema_version": 1,
            "product": "EBBot",
            "release_enabled": False,
            "approved_signer_thumbprints": [],
            "required_targets": list(TARGETS),
        }
        self.observation = {
            "schema_version": 1,
            "platform": "windows",
            "product": "EBBot",
            "version": "3.21.0",
            "signatures": {
                target: {
                    "present": True,
                    "status": "NotSigned",
                    "thumbprint": None,
                    "valid_from": None,
                    "valid_until": None,
                }
                for target in TARGETS
            },
        }

    def _make_valid(self):
        for entry in self.observation["signatures"].values():
            entry.update({
                "status": "Valid",
                "thumbprint": self.fingerprint,
                "valid_from": "2026-01-01T00:00:00+00:00",
                "valid_until": "2027-01-01T00:00:00+00:00",
            })

    def test_unsigned_package_is_blocked(self):
        result = audit(self.policy, self.observation, at=self.now)
        self.assertEqual(result["signing_validation"], "BLOCKED")
        self.assertEqual(result["release_status"], "BLOCKED")
        self.assertFalse(result["enables_updates"])
        self.assertFalse(result["executes_binary"])
        self.assertFalse(result["publishes_release"])

    def test_valid_authenticode_unknown_signer_is_still_blocked(self):
        self._make_valid()
        result = audit(self.policy, self.observation, at=self.now)
        self.assertEqual(result["signing_validation"], "BLOCKED")
        self.assertTrue(any(
            "allowlist" in reason
            for item in result["signature_checks"] for reason in item["reasons"]
        ))

    def test_allowlisted_windows_signature_never_enables_publication(self):
        self._make_valid()
        self.policy["approved_signer_thumbprints"] = [self.fingerprint]
        result = audit(self.policy, self.observation, at=self.now)
        self.assertEqual(result["signing_validation"], "PASSED")
        self.assertEqual(result["release_status"], "BLOCKED")
        self.assertFalse(result["publishes_release"])

    def test_expired_certificate_fails_even_when_thumbprint_pinned(self):
        self._make_valid()
        self.policy["approved_signer_thumbprints"] = [self.fingerprint]
        self.observation["signatures"]["nsis_installer"]["valid_until"] = "2026-01-02T00:00:00Z"
        self.assertEqual(audit(self.policy, self.observation, at=self.now)["signing_validation"],
                         "BLOCKED")

    def test_missing_backend_and_extra_target_block_validation(self):
        self._make_valid()
        self.policy["approved_signer_thumbprints"] = [self.fingerprint]
        del self.observation["signatures"]["python_backend"]
        self.observation["signatures"]["unexpected_exe"] = {}
        result = audit(self.policy, self.observation, at=self.now)
        self.assertEqual(result["signing_validation"], "BLOCKED")
        self.assertTrue(any("exactly the three" in error for error in result["release_blockers"]))

    def test_release_enabled_policy_is_rejected(self):
        self._make_valid()
        self.policy["approved_signer_thumbprints"] = [self.fingerprint]
        self.policy["release_enabled"] = True
        self.assertEqual(audit(self.policy, self.observation, at=self.now)["signing_validation"],
                         "BLOCKED")

    def test_partial_allowlist_never_approves_unknown_certificate(self):
        self._make_valid()
        self.policy["approved_signer_thumbprints"] = ["B" * 40]
        self.assertEqual(audit(self.policy, self.observation, at=self.now)["signing_validation"],
                         "BLOCKED")


if __name__ == "__main__":
    unittest.main()
