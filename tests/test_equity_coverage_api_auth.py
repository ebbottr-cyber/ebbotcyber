"""Actual ASGI coverage route: administrator session, privacy and read-only behavior.

This test creates only a small in-memory FastAPI app with the real data router
and real authentication middleware; it never starts the EBBot scheduler.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.middlewares.auth import add_auth_middleware
from api.v1.endpoints.data import router as data_router
from src.auth import COOKIE_NAME


def report_fixture() -> dict:
    market_data = {
        "candidate_instruments": 1,
        "stocks": 1,
        "etfs": 0,
        "with_any_ohlcv": 0,
        "with_min_bars": 0,
        "with_recent_bar": 0,
        "undated_inventory_count": 1,
        "missing_ohlcv_count": 1,
        "insufficient_history_count": 0,
        "stale_ohlcv_count": 0,
        "missing_symbols": ["DO_NOT_SEND_THIS_TICKER"],
    }
    return {
        "status": "BLOCKED_INCOMPLETE_EVIDENCE",
        "as_of_utc_date": "2026-11-21",
        "selected_markets": ["tr", "us", "de", "hk"],
        "markets": {key: dict(market_data) for key in ("tr", "us", "de", "hk")},
        "total_candidate_instruments": 4,
        "orders": 0,
    }


class EquityCoverageAuthIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "private-evidence.json"
        self.path.write_text(json.dumps(report_fixture()), encoding="utf-8")
        self.app = FastAPI()
        self.app.include_router(data_router, prefix="/api/v1/data")
        add_auth_middleware(self.app)
        self.endpoint = "/api/v1/data/equity-coverage"

    def _auth(self, enabled: bool):
        return (
            patch("api.middlewares.auth.is_auth_enabled", return_value=enabled),
            patch("api.v1.endpoints.data.is_auth_enabled", return_value=enabled),
            patch("api.middlewares.auth.verify_session", side_effect=lambda x: x == "valid-session"),
            patch.dict(os.environ, {
                "EBBOT_EQUITY_COVERAGE_REPORT_PATH": str(self.path),
            }),
        )

    def test_admin_auth_enabled_missing_cookie_returns_401_without_reading_file(self):
        a, b, c, d = self._auth(True)
        with a, b, c, d, patch(
            "src.services.equity_data_coverage_reader.read_equity_coverage_report",
            side_effect=AssertionError("file must not be opened"),
        ):
            with TestClient(self.app) as client:
                response = client.get(self.endpoint)
                self.assertEqual(response.status_code, 401)
                self.assertNotIn("DO_NOT_SEND_THIS_TICKER", response.text)

    def test_invalid_cookie_denied_even_if_report_file_exists(self):
        a, b, c, d = self._auth(True)
        with a, b, c, d:
            with TestClient(self.app) as client:
                response = client.get(
                    self.endpoint, cookies={COOKIE_NAME: "invalid-session"},
                )
                self.assertEqual(response.status_code, 401)

    def test_valid_session_receives_aggregates_only_and_no_cache(self):
        a, b, c, d = self._auth(True)
        with a, b, c, d:
            with TestClient(self.app) as client:
                response = client.get(
                    self.endpoint, cookies={COOKIE_NAME: "valid-session"},
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers.get("cache-control"), "no-store")
                body = response.json()
                self.assertIn(body["status"], {"unverified", "stale"})
                self.assertEqual(body["total_candidate_instruments"], 4)
                self.assertEqual(body["markets"]["tr"]["missing_ohlcv_count"], 1)
                self.assertFalse(body["licensed_ohlcv_verified"])
                self.assertFalse(body["live_trading_enabled"])
                self.assertFalse(body["paper_trading_enabled"])
                self.assertNotIn("DO_NOT_SEND_THIS_TICKER", response.text)
                self.assertNotIn(str(self.path), response.text)

    def test_admin_auth_disabled_never_reads_local_report(self):
        a, b, c, d = self._auth(False)
        with a, b, c, d, patch(
            "src.services.equity_data_coverage_reader.read_equity_coverage_report",
            side_effect=AssertionError("auth-off must never read local report"),
        ):
            with TestClient(self.app) as client:
                response = client.get(self.endpoint)
                self.assertEqual(response.status_code, 200)
                body = response.json()
                self.assertEqual(body["status"], "unavailable")
                self.assertEqual(body["reason"], "administrator_auth_required")
                self.assertEqual(body["markets"], {})
                self.assertIsNone(body["total_candidate_instruments"])
                self.assertEqual(response.headers.get("cache-control"), "no-store")

    def test_untrusted_query_cannot_switch_report_path(self):
        other = Path(self.folder.name) / "other.json"
        different = report_fixture()
        different["total_candidate_instruments"] = 999
        other.write_text(json.dumps(different), encoding="utf-8")
        a, b, c, d = self._auth(True)
        with a, b, c, d:
            with TestClient(self.app) as client:
                response = client.get(
                    self.endpoint,
                    params={"path": str(other), "report_json": str(other)},
                    cookies={COOKIE_NAME: "valid-session"},
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["total_candidate_instruments"], 4)

    def test_non_get_method_does_not_modify_operator_report(self):
        original = self.path.read_bytes()
        a, b, c, d = self._auth(True)
        with a, b, c, d:
            with TestClient(self.app) as client:
                response = client.post(
                    self.endpoint,
                    cookies={COOKIE_NAME: "valid-session"},
                    json={"status": "FULLY_VERIFIED"},
                )
                self.assertEqual(response.status_code, 405)
        self.assertEqual(self.path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
