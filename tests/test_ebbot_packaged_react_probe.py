"""Read-only Turkish React CI fixture never registers production API routes."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app import create_app, _is_ebbot_packaged_react_probe


class FrozenReactProbeTests(unittest.TestCase):
    def _fixture(self, root: Path) -> Path:
        root.mkdir(parents=True, exist_ok=True)
        (root / "index.html").write_text(
            '<!doctype html><html lang="tr"><body><div id="root"></div></body></html>',
            encoding="utf-8",
        )
        (root / "assets").mkdir(exist_ok=True)
        (root / "assets" / "app.js").write_text(
            "console.log('read-only react test');", encoding="utf-8"
        )
        return root

    def test_frozen_react_ui_serves_only_assets_and_synthetic_readonly_fixtures(self):
        with tempfile.TemporaryDirectory() as tmp:
            static_dir = self._fixture(Path(tmp) / "static")
            with (
                patch.dict(os.environ, {
                    "EBBOT_PACKAGED_HEALTH_PROBE": "1",
                    "EBBOT_PACKAGED_REACT_PROBE": "1",
                    "GITHUB_ACTIONS": "true",
                }),
                patch.object(sys, "frozen", True, create=True),
            ):
                app = create_app(static_dir=static_dir)
                with TestClient(app) as client:
                    for path in (
                        "/", "/usage", "/data",
                        "/portfolio", "/decision-signals", "/screening", "/settings",
                    ):
                        result = client.get(path)
                        self.assertEqual(result.status_code, 200, path)
                        self.assertIn('lang="tr"', result.text)
                    js = client.get("/assets/app.js")
                    self.assertEqual(js.status_code, 200)
                    self.assertIn("javascript", js.headers.get("content-type", ""))
                    self.assertEqual(js.text, "console.log('read-only react test');")
                    auth = client.get("/api/v1/auth/status")
                    self.assertEqual(auth.status_code, 200)
                    self.assertEqual(auth.json(), {
                        "authEnabled": False,
                        "loggedIn": False,
                        "passwordSet": False,
                        "passwordChangeable": False,
                        "setupState": "no_password",
                    })
                    self.assertEqual(
                        client.get("/api/health").json(),
                        {"status": "ok", "probe": "offline-packaged"},
                    )
                    accounts = client.get("/api/v1/portfolio/accounts")
                    self.assertEqual(accounts.status_code, 200)
                    self.assertEqual(len(accounts.json()["accounts"]), 1)
                    self.assertEqual(accounts.json()["accounts"][0]["name"], "CI Örnek Hesap (sanal)")
                    config = client.get("/api/v1/system/config?include_schema=true")
                    self.assertEqual(config.status_code, 200)
                    self.assertEqual(config.json()["configVersion"], "ci-readonly-no-save")
                    self.assertEqual(
                        [item["schema"]["category"] for item in config.json()["items"]],
                        ["base", "data_source"],
                    )
                    self.assertTrue(
                        all(not item["schema"]["isEditable"] for item in config.json()["items"])
                    )
                    for path in (
                        "/api/v1/analysis/analyze",
                        "/api/v1/portfolio/snapshot",
                        "/api/v1/portfolio/risk",
                        "/api/v1/system/config/export",
                        "/api/v1/screening/run",
                        "/api/v1/health",
                        "/docs", "/openapi.json",
                        "/assets/missing.js",
                    ):
                        self.assertEqual(client.get(path).status_code, 404, path)
                    for path in (
                        "/api/v1/analysis/analyze",
                        "/api/v1/portfolio/accounts",
                        "/api/v1/system/config",
                        "/api/v1/auth/login",
                        "/api/v1/auth/status",
                        "/api/v1/screening/run",
                        "/api/v1/settings/config",
                        "/portfolio",
                        "/decision-signals",
                        "/screening",
                        "/settings",
                    ):
                        self.assertEqual(
                            client.post(path).status_code,
                            405 if path in (
                                "/api/v1/auth/status",
                                "/api/v1/portfolio/accounts",
                                "/api/v1/system/config",
                                "/portfolio", "/decision-signals", "/screening", "/settings",
                            ) else 404,
                            path,
                        )
                    for path in ("/api/v1/portfolio/accounts", "/api/v1/system/config"):
                        for method in (client.put, client.delete, client.patch):
                            self.assertEqual(method(path).status_code, 405, path)
                    self.assertIsNone(
                        getattr(app.state, "runtime_scheduler_service", None)
                    )
                    self.assertIsNone(
                        getattr(app.state, "stock_index_refresh_task", None)
                    )

    def test_react_mode_requires_frozen_github_actions_and_health_mode(self):
        with patch.object(sys, "frozen", True, create=True):
            for env in (
                {"EBBOT_PACKAGED_HEALTH_PROBE": "1",
                 "EBBOT_PACKAGED_REACT_PROBE": "0", "GITHUB_ACTIONS": "true"},
                {"EBBOT_PACKAGED_HEALTH_PROBE": "0",
                 "EBBOT_PACKAGED_REACT_PROBE": "1", "GITHUB_ACTIONS": "true"},
                {"EBBOT_PACKAGED_HEALTH_PROBE": "1",
                 "EBBOT_PACKAGED_REACT_PROBE": "1", "GITHUB_ACTIONS": "false"},
            ):
                with patch.dict(os.environ, env):
                    self.assertFalse(_is_ebbot_packaged_react_probe())


if __name__ == "__main__":
    unittest.main()
