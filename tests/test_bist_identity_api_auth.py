"""ASGI security checks for the actual BIST identity read-only API route."""
from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.middlewares.auth import add_auth_middleware
from api.v1.endpoints.data import router as data_router
from src.auth import COOKIE_NAME
# Resolve the fixture consistently in unittest discovery and pytest.
from tests.test_bist_identity_report_reader import fixture


class BistIdentityEndpointAuthTests(unittest.TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.private_path = Path(self.folder.name) / "bist-private.json"
        self.private_path.write_text(json.dumps(fixture()), encoding="utf-8")
        self.app = FastAPI()
        self.app.include_router(data_router, prefix="/api/v1/data")
        add_auth_middleware(self.app)
        self.path = "/api/v1/data/bist-identity"

    def auth(self, enabled: bool):
        return (
            patch("api.middlewares.auth.is_auth_enabled", return_value=enabled),
            patch("api.v1.endpoints.data.is_auth_enabled", return_value=enabled),
            patch("api.middlewares.auth.verify_session", side_effect=lambda x: x == "ok-admin"),
            patch.dict(os.environ, {
                "EBBOT_BIST_IDENTITY_REPORT_PATH": str(self.private_path),
            }),
        )

    def test_no_cookie_auth_enabled_blocks_before_opening_private_file(self):
        a, b, c, d = self.auth(True)
        with a, b, c, d, patch(
            "src.services.bist_identity_report_reader.read_bist_identity_summary",
            side_effect=AssertionError("must not open private source"),
        ):
            with TestClient(self.app) as client:
                response = client.get(self.path)
        self.assertEqual(response.status_code, 401)

    def test_invalid_admin_session_blocks(self):
        a, b, c, d = self.auth(True)
        with a, b, c, d:
            with TestClient(self.app) as client:
                response = client.get(self.path, cookies={COOKIE_NAME: "bad-admin"})
        self.assertEqual(response.status_code, 401)

    def test_valid_admin_returns_only_counts_and_no_store(self):
        a, b, c, d = self.auth(True)
        with a, b, c, d:
            with TestClient(self.app) as client:
                response = client.get(self.path, cookies={COOKIE_NAME: "ok-admin"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Cache-Control"), "no-store")
        result = response.json()
        self.assertEqual(result["status"], "unverified")
        self.assertEqual(result["counts"]["kap_candidate_count"], 3)
        self.assertEqual(result["counts"]["exchange_active_count"], 2)
        self.assertEqual(result["counts"]["active_with_ohlcv_in_supplied_file_count"], 1)
        self.assertNotIn("PRIVATE_", response.text)
        self.assertNotIn("candidate_symbol_details", response.text)
        self.assertNotIn(str(self.private_path), response.text)
        self.assertFalse(result["independent_listing_verified"])
        self.assertFalse(result["licensed_prices_verified"])
        self.assertFalse(result["live_trading_enabled"])

    def test_auth_disabled_discloses_no_report_data_and_does_not_read(self):
        a, b, c, d = self.auth(False)
        with a, b, c, d, patch(
            "src.services.bist_identity_report_reader.read_bist_identity_summary",
            side_effect=AssertionError("must not read without auth"),
        ):
            with TestClient(self.app) as client:
                response = client.get(self.path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Cache-Control"), "no-store")
        self.assertEqual(response.json()["reason"], "administrator_auth_required")
        self.assertIsNone(response.json()["counts"])
        self.assertNotIn("PRIVATE_", response.text)

    def test_untrusted_query_parameters_cannot_open_other_file(self):
        wrong_path = Path(self.folder.name) / "override.json"
        data = fixture()
        data["kap_candidate_count"] = 90000
        wrong_path.write_text(json.dumps(data), encoding="utf-8")
        a, b, c, d = self.auth(True)
        with a, b, c, d:
            with TestClient(self.app) as client:
                response = client.get(
                    self.path,
                    cookies={COOKIE_NAME: "ok-admin"},
                    params={"path": str(wrong_path), "file": str(wrong_path)},
                )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["counts"]["kap_candidate_count"], 3)

    def test_post_method_does_not_touch_local_report(self):
        original = self.private_path.read_bytes()
        a, b, c, d = self.auth(True)
        with a, b, c, d:
            with TestClient(self.app) as client:
                response = client.post(
                    self.path,
                    cookies={COOKIE_NAME: "ok-admin"},
                    json={"independent_listing_verified": True},
                )
        self.assertEqual(response.status_code, 405)
        self.assertEqual(self.private_path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
