"""Source Paper V2 handshake must never enable EBBot execution.

No network, no writes. An unknown/legacy upstream is explicitly unavailable.
"""
import unittest
from unittest.mock import AsyncMock, patch
from src.services import crypto_paper_bridge as p


def response(enabled=False):
    return {
        "mode": "paper_only", "source": "Trading Office",
        "protocol": "paper_v2_atomic_sqlite",
        "paper_execution_permitted": enabled,
        "legacy_paper_writes_enabled": False,
        "real_exchange_orders": False,
        "requires_admin_auth": True,
        "risk_check_location": "same_sqlite_transaction",
    }


class PaperV2HandshakeTests(unittest.IsolatedAsyncioTestCase):
    async def test_valid_source_protocol_is_detected_but_ebbot_remains_read_only(self):
        get = AsyncMock(return_value=response(True))
        with patch.object(p, "_get", get):
            out = await p.read_paper_v2_capabilities()
        self.assertTrue(out["upstream_v2_present"])
        self.assertTrue(out["upstream_v2_opted_in"])
        self.assertFalse(out["ebbot_paper_execution_permitted"])
        self.assertFalse(out["real_exchange_orders"])
        self.assertEqual(get.await_args.args[0], "v2-capabilities")
        self.assertEqual(p._ALLOWED["v2-capabilities"], "/api/v1/paper/v2/capabilities")

    async def test_legacy_upstream_or_missing_protocol_reports_unavailable(self):
        for output in (
            {"mode": "paper_only"}, {**response(), "real_exchange_orders": True},
            {**response(), "legacy_paper_writes_enabled": True},
            {**response(), "requires_admin_auth": False},
        ):
            with self.subTest(output=output), patch.object(p, "_get", AsyncMock(return_value=output)):
                out = await p.read_paper_v2_capabilities()
                self.assertFalse(out["upstream_v2_present"])
                self.assertFalse(out["ebbot_paper_execution_permitted"])

    async def test_connection_failure_does_not_create_fake_readiness(self):
        with patch.object(p, "_get", AsyncMock(side_effect=p.PaperReadError("upstream_unavailable"))):
            result = await p.read_paper_v2_capabilities()
        self.assertFalse(result["upstream_v2_present"])
        self.assertFalse(result["upstream_v2_opted_in"])
        self.assertEqual(result["execution"], "disabled")


if __name__ == "__main__":
    unittest.main()
