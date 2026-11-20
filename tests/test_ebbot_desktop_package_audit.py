"""Unit contracts for an offline Windows Electron packaging audit."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.audit_ebbot_desktop_package import audit, package_audit, source_audit


class DesktopPackageAuditTests(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.root = Path(d.name)
        desktop = self.root / "apps/dsa-desktop"
        desktop.mkdir(parents=True)
        (desktop / "package.json").write_text(json.dumps({
            "version": "3.21.0",
            "build": {
                "appId": "com.daily-stock-analysis.desktop",
                "productName": "Daily Stock Analysis",
                "win": {"target": "nsis", "publish": [
                    {"provider": "github", "owner": "ZhuLinsen", "repo": "daily_stock_analysis"}
                ]},
                "files": ["main.js", "preload.js"],
                "extraResources": [
                    {"from": "../../dist/backend/stock_analysis", "to": "backend/stock_analysis"}
                ],
            }
        }), encoding="utf-8")
        (desktop / "main.js").write_text(
            "const GITHUB_OWNER = 'ZhuLinsen';\n"
            "const GITHUB_REPO = 'daily_stock_analysis';\n",
            encoding="utf-8",
        )
        self.dist = desktop / "dist"

    def _create_sample_package(self):
        self.dist.mkdir(parents=True, exist_ok=True)
        installer = self.dist / "daily-stock-analysis-windows-installer-v3.21.0.exe"
        installer.write_bytes(b"synthetic-test-installer")
        (self.dist / (installer.name + ".blockmap")).write_bytes(b"mock")
        (self.dist / "latest.yml").write_text(
            "version: 3.21.0\n"
            "files:\n"
            "  - url: daily-stock-analysis-windows-installer-v3.21.0.exe\n"
            "    sha512: synthetic\n"
            "path: daily-stock-analysis-windows-installer-v3.21.0.exe\n"
            "sha512: synthetic\n",
            encoding="utf-8",
        )
        resources = self.dist / "win-unpacked/resources"
        (resources / "backend/stock_analysis/_internal/static").mkdir(parents=True)
        (resources / "backend/stock_analysis/stock_analysis.exe").write_bytes(b"not a real binary")
        (resources / "backend/stock_analysis/_internal/static/index.html").write_text("test")
        (resources / ".env.example").write_text("# no secrets")
        (resources / "app.asar").write_bytes(b"fixture")

    def test_source_upstream_references_block_release(self):
        result = source_audit(self.root)
        self.assertTrue(all(x["passed"] for x in result["checks"]))
        self.assertTrue(any("upstream" in x for x in result["release_blockers"]))
        self.assertTrue(any("code-signing" in x for x in result["release_blockers"]))
        self.assertEqual(audit(self.root)["release_status"], "BLOCKED")

    def test_missing_dist_is_not_misreported_as_passed(self):
        result = package_audit(self.root, self.dist, "3.21.0")
        self.assertEqual(result["package_validation"], "FAILED")
        self.assertFalse(result["sha256"])
        self.assertTrue(any(x["name"] == "real_backend_exe" and not x["passed"]
                            for x in result["checks"]))

    def test_synthetic_complete_file_set_passes_structure_but_never_release(self):
        self._create_sample_package()
        result = audit(self.root, self.dist)
        self.assertEqual(result["package"]["package_validation"], "PASSED")
        self.assertIn("daily-stock-analysis-windows-installer-v3.21.0.exe",
                      result["package"]["sha256"])
        self.assertEqual(result["release_status"], "BLOCKED")
        self.assertFalse(result["publishes_release"])
        self.assertFalse(result["starts_electron"])
        self.assertFalse(result["enables_trading"])

    def test_bad_updater_metadata_blocks_package(self):
        self._create_sample_package()
        latest = self.dist / "latest.yml"
        latest.write_text(latest.read_text().replace("version: 3.21.0", "version: 9.9.9"))
        self.assertEqual(package_audit(self.root, self.dist, "3.21.0")["package_validation"],
                         "FAILED")

    def test_real_user_configuration_must_not_be_packaged(self):
        self._create_sample_package()
        env = self.dist / "win-unpacked/resources/.env"
        env.write_text("SECRET=do-not-ship")
        r = package_audit(self.root, self.dist, "3.21.0")
        self.assertEqual(r["package_validation"], "FAILED")
        self.assertFalse(next(x["passed"] for x in r["checks"] if x["name"] == "no_user_env"))


if __name__ == "__main__":
    unittest.main()
