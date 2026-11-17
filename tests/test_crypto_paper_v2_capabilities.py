"""Paper V2 source claims do not enable EBBot orders.

An absent protocol and a transport outage MUST NOT both be silently turned
into a fresh-looking 'not installed' result. Source claims are never proof
of executable safety. No network, exchange credentials, or writes.
"""
import unittest

from src.services import crypto_paper_v2_status as p


def source(enabled=False):
    return {
        "mode": "paper_only", "source": "Trading Office",
        "protocol": "paper_v2_atomic_sqlite",
        "paper_execution_permitted": enabled,
        "legacy_paper_writes_enabled": False,
        "real_exchange_orders": False,
        "requires_admin_auth": True,
        "risk_check_location": "same_sqlite_transaction",
    }


class SourceClaimTests(unittest.TestCase):
    def test_installed_source_on_flag_never_grants_ebbot_execution(self):
        result = p.verify_capabilities(source(True))
        self.assertEqual(result["source_state"], "SOURCE_FLAG_ON_UNVERIFIED")
        self.assertFalse(result["readiness_verified"])
        self.assertFalse(result["paper_execution_permitted"])
        self.assertFalse(result["ebbot_paper_writes_enabled"])
        self.assertFalse(result["real_exchange_orders"])

    def test_installed_source_disabled_is_reported_as_disabled(self):
        result = p.verify_capabilities(source())
        self.assertEqual(result["source_state"], "SOURCE_INSTALLED_DISABLED")
        self.assertFalse(result["paper_execution_permitted"])

    def test_missing_or_unsafe_source_has_no_fallback(self):
        invalid = (
            {"mode": "paper_only"},
            {**source(), "real_exchange_orders": True},
            {**source(), "legacy_paper_writes_enabled": True},
            {**source(), "requires_admin_auth": False},
            {**source(), "risk_check_location": "outside_sqlite"},
        )
        for raw in invalid:
            with self.subTest(raw=raw), self.assertRaises(p.PaperV2StatusUnavailable):
                p.verify_capabilities(raw)


if __name__ == "__main__":
    unittest.main()
