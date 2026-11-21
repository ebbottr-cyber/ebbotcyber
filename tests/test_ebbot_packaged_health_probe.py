"""Offline packaged health probe safety contracts (no market/network calls)."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


REPO = Path(__file__).resolve().parent.parent


class PackagedHealthProbeTests(unittest.TestCase):
    def test_health_route_is_the_only_api_route_in_packaged_ci_mode(self):
        from api.app import create_app
        from fastapi.testclient import TestClient

        with (
            patch.dict(os.environ, {
                "EBBOT_PACKAGED_HEALTH_PROBE": "1",
                "GITHUB_ACTIONS": "true",
            }),
            patch.object(sys, "frozen", True, create=True),
        ):
            app = create_app()
            with TestClient(app) as client:
                response = client.get("/api/health")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {
                    "status": "ok", "probe": "offline-packaged",
                })
                self.assertEqual(
                    client.get("/api/v1/analysis/analyze").status_code, 404
                )
                self.assertEqual(
                    client.get("/api/v1/health").status_code, 404
                )
                self.assertEqual(client.get("/docs").status_code, 404)
                self.assertEqual(client.get("/openapi.json").status_code, 404)
                self.assertIsNone(getattr(app.state, "runtime_scheduler_service", None))
                self.assertIsNone(getattr(app.state, "stock_index_refresh_task", None))

    def test_probe_requires_frozen_ci_and_explicit_opt_in(self):
        from api.app import _is_ebbot_packaged_health_probe
        with (
            patch.dict(os.environ, {
                "EBBOT_PACKAGED_HEALTH_PROBE": "1",
                "GITHUB_ACTIONS": "false",
            }),
            patch.object(sys, "frozen", True, create=True),
        ):
            self.assertFalse(_is_ebbot_packaged_health_probe())
        with (
            patch.dict(os.environ, {
                "EBBOT_PACKAGED_HEALTH_PROBE": "0",
                "GITHUB_ACTIONS": "true",
            }),
            patch.object(sys, "frozen", True, create=True),
        ):
            self.assertFalse(_is_ebbot_packaged_health_probe())
        with (
            patch.dict(os.environ, {
                "EBBOT_PACKAGED_HEALTH_PROBE": "1",
                "GITHUB_ACTIONS": "true",
            }),
            patch.object(sys, "frozen", False, create=True),
        ):
            self.assertFalse(_is_ebbot_packaged_health_probe())

    def test_main_ci_restrictions_and_no_bot_clients(self):
        source = (REPO / "main.py").read_text(encoding="utf-8")
        self.assertIn('os.getenv("EBBOT_PACKAGED_HEALTH_PROBE") == "1"', source)
        self.assertIn('sys.argv[1:] == expected_args', source)
        self.assertIn('if bot_clients_started and not offline_health_probe:', source)
        self.assertIn('if not offline_health_probe and not prepare_webui_frontend_assets()', source)

    def test_probe_never_uses_external_health_hosts_or_trades(self):
        source = (REPO / "scripts/probe_ebbot_packaged_health.py").read_text(encoding="utf-8")
        self.assertIn('http.client.HTTPConnection("127.0.0.1"', source)
        self.assertIn('"--serve-only", "--host", "127.0.0.1"', source)
        self.assertIn('env=_sanitized_environment()', source)
        self.assertIn('"/api/v1/analysis/analyze"', source)
        self.assertNotIn('subprocess.run(["powershell"', source)


if __name__ == "__main__":
    unittest.main()
