"""Fail-closed read-only Paper V2 capability handshake tests.

A source JSON claim is NOT an independent readiness attestation and must not
grant EBBot a paper or live execution API. No network or order methods used.
"""
from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import httpx

from src.services import crypto_paper_v2_status as v2


def valid_source(enabled=False):
    return {
        "mode": "paper_only",
        "source": "Trading Office",
        "protocol": "paper_v2_atomic_sqlite",
        "paper_execution_permitted": enabled,
        "legacy_paper_writes_enabled": False,
        "real_exchange_orders": False,
        "risk_check_location": "same_sqlite_transaction",
        "requires_admin_auth": True,
        "note": "This upstream capability is a claim, not authorization.",
    }


class V2StatusValidationTests(unittest.TestCase):
    def test_disabled_source_is_observed_without_ebbot_permissions(self):
        out = v2.verify_capabilities(valid_source())
        self.assertEqual(out["source_state"], "SOURCE_INSTALLED_DISABLED")
        self.assertFalse(out["readiness_verified"])
        self.assertFalse(out["paper_execution_permitted"])
        self.assertFalse(out["ebbot_paper_writes_enabled"])
        self.assertEqual(out["execution"], "disabled")

    def test_opted_in_source_cannot_enable_ebbot_order_path(self):
        out = v2.verify_capabilities(valid_source(enabled=True))
        self.assertEqual(out["source_state"], "SOURCE_FLAG_ON_UNVERIFIED")
        self.assertTrue(out["source_flag_claimed_enabled"])
        self.assertFalse(out["readiness_verified"])
        self.assertFalse(out["paper_execution_permitted"])
        self.assertFalse(out["real_exchange_orders"])

    def test_untrusted_capability_fields_are_rejected(self):
        for key, value in (
            ("mode", "live"),
            ("source", "other"),
            ("protocol", "paper_v1"),
            ("paper_execution_permitted", 1),
            ("legacy_paper_writes_enabled", True),
            ("real_exchange_orders", True),
            ("risk_check_location", "outside_sqlite"),
            ("requires_admin_auth", False),
        ):
            with self.subTest(key=key), self.assertRaises(v2.PaperV2StatusUnavailable):
                v2.verify_capabilities({**valid_source(), key: value})
        with self.assertRaises(v2.PaperV2StatusUnavailable):
            v2.verify_capabilities([])


class V2StatusHttpTests(unittest.IsolatedAsyncioTestCase):
    async def _read_with(self, responder):
        actual = httpx.AsyncClient
        seen = []

        def client(*args, **kwargs):
            self.assertFalse(kwargs.get("follow_redirects"))
            self.assertFalse(kwargs.get("trust_env"))
            return actual(*args, transport=httpx.MockTransport(responder), **kwargs)

        with patch.object(
            v2, "_connection_settings", return_value=("http://127.0.0.1:8154", "r" * 40)
        ), patch.object(v2.httpx, "AsyncClient", side_effect=client):
            return await v2.read_v2_status()

    async def test_only_fixed_get_to_readonly_capabilities(self):
        def responder(req):
            self.assertEqual(req.method, "GET")
            self.assertEqual(req.url.path, v2.CAPABILITY_PATH)
            self.assertEqual(req.url.host, "127.0.0.1")
            self.assertEqual(req.headers.get("x-api-key"), "r" * 40)
            self.assertNotIn("paper/v2/execute", req.url.path)
            return httpx.Response(
                200, headers={"Content-Type": "application/json"},
                content=json.dumps(valid_source()).encode("utf-8"),
            )

        result = await self._read_with(responder)
        self.assertEqual(result["source_state"], "SOURCE_INSTALLED_DISABLED")

    async def test_source_missing_vs_down_are_not_falsely_claimed_installed(self):
        def missing(req):
            return httpx.Response(404, headers={"Content-Type": "application/json"}, json={})
        with self.assertRaises(v2.PaperV2StatusUnavailable) as ctx:
            await self._read_with(missing)
        self.assertEqual(ctx.exception.code, "paper_v2_not_installed")

        def down(req):
            return httpx.Response(503, headers={"Content-Type": "application/json"}, json={})
        with self.assertRaises(v2.PaperV2StatusUnavailable) as ctx:
            await self._read_with(down)
        self.assertEqual(ctx.exception.code, "paper_v2_unavailable")

    async def test_rejects_wrong_content_type_malformed_json_and_oversize(self):
        for response in (
            httpx.Response(200, headers={"Content-Type": "text/plain"}, text="okay"),
            httpx.Response(200, headers={"Content-Type": "application/json"}, content=b"{"),
            httpx.Response(
                200, headers={"Content-Type": "application/json"},
                content=b" " * (v2.MAX_RESPONSE_BYTES + 1),
            ),
        ):
            with self.subTest(status=response.status_code):
                with self.assertRaises(v2.PaperV2StatusUnavailable):
                    await self._read_with(lambda req, r=response: r)


if __name__ == "__main__":
    unittest.main()
