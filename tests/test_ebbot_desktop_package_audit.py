"""Unit contracts for an offline Windows Electron packaging audit."""
from __future__ import annotations

import base64
import hashlib
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
            "name": "ebbot-desktop",
            "build": {
                "appId": "com.ebbot.desktop",
                "productName": "EBBot",
                "win": {"target": "nsis", "artifactName": "EBBot-windows-installer-v${version}.${ext}", "publish": [
                    {"provider": "github", "owner": "ebbottr-cyber", "repo": "ebbotcyber"}
                ]},
                "files": ["main.js", "preload.js", "sqliteSnapshotBridge.js"],
                "extraResources": [
                    {"from": "../../dist/backend/stock_analysis", "to": "backend/stock_analysis"}
                ],
            }
        }), encoding="utf-8")
        (desktop / "main.js").write_text(
            "const GITHUB_OWNER = 'ebbottr-cyber';\n"
            "const GITHUB_REPO = 'ebbotcyber';\n"
            "const DESKTOP_UPDATES_ENABLED = false;\n"
            "const sqliteSnapshotBridge = require('./sqliteSnapshotBridge');\n"
            "function a() { if (!DESKTOP_UPDATES_ENABLED) {} }\n"
            "function b() { if (!DESKTOP_UPDATES_ENABLED) {} }\n",
            encoding="utf-8",
        )
        (desktop / "sqliteSnapshotBridge.js").write_text(
            "function stageSnapshotRestoreCandidate() {}\n",
            encoding="utf-8",
        )
        loading = desktop / "renderer/loading.html"
        loading.parent.mkdir(parents=True)
        loading.write_text('<title>EBBot</title><h1 class="title">EBBot</h1>', encoding="utf-8")
        self.dist = desktop / "dist"

    def _create_sample_package(self):
        self.dist.mkdir(parents=True, exist_ok=True)
        installer = self.dist / "EBBot-windows-installer-v3.21.0.exe"
        data = b"synthetic-test-installer"
        installer.write_bytes(data)
        digest = base64.b64encode(hashlib.sha512(data).digest()).decode("ascii")
        (self.dist / (installer.name + ".blockmap")).write_bytes(b"mock")
        (self.dist / "latest.yml").write_text(
            "version: 3.21.0\n"
            "files:\n"
            "  - url: EBBot-windows-installer-v3.21.0.exe\n"
            f"    sha512: {digest}\n"
            f"    size: {len(data)}\n"
            "path: EBBot-windows-installer-v3.21.0.exe\n"
            f"sha512: {digest}\n",
            encoding="utf-8",
        )
        resources = self.dist / "win-unpacked/resources"
        (resources / "backend/stock_analysis/_internal/static").mkdir(parents=True)
        (resources / "backend/stock_analysis/stock_analysis.exe").write_bytes(b"not a real binary")
        (resources / "backend/stock_analysis/_internal/static/index.html").write_text("test")
        (resources / ".env.example").write_text("# no secrets")
        (resources / "app.asar").write_bytes(b"fixture")

    def test_source_identity_and_disabled_updater_are_checked(self):
        result = source_audit(self.root)
        self.assertTrue(all(x["passed"] for x in result["checks"]))
        self.assertTrue(any(x["name"] == "updater_runtime_disabled" and x["passed"]
                            for x in result["checks"]))
        self.assertTrue(any(x["name"] == "ebbot_publish_target" and x["passed"]
                            for x in result["checks"]))
        self.assertTrue(any("code-signing" in x for x in result["release_blockers"]))
        self.assertEqual(audit(self.root)["release_status"], "BLOCKED")

    def test_offline_sqlite_bridge_must_be_packaged(self):
        desktop = self.root / "apps/dsa-desktop"
        (desktop / "sqliteSnapshotBridge.js").unlink()
        result = source_audit(self.root)
        self.assertFalse(next(check["passed"] for check in result["checks"]
                              if check["name"] == "sqlite_offline_bridge_packaged"))

    def test_legacy_loading_screen_fails_source_audit(self):
        loading = self.root / "apps/dsa-desktop/renderer/loading.html"
        loading.write_text('<title>Daily Stock Analysis</title><h1 class="title">Daily Stock Analysis</h1>',
                           encoding="utf-8")
        self.assertFalse(next(x["passed"] for x in source_audit(self.root)["checks"]
                              if x["name"] == "ebbot_loading_window"))

    def test_upstream_or_enabled_updater_fails_strict_source(self):
        desktop = self.root / "apps/dsa-desktop"
        main_js = desktop / "main.js"
        original = main_js.read_text(encoding="utf-8")
        main_js.write_text(original.replace("const GITHUB_OWNER = 'ebbottr-cyber';",
                                            "const GITHUB_OWNER = 'ZhuLinsen';"),
                           encoding="utf-8")
        self.assertFalse(next(x["passed"] for x in source_audit(self.root)["checks"]
                              if x["name"] == "ebbot_update_references"))
        main_js.write_text(original.replace("const DESKTOP_UPDATES_ENABLED = false;",
                                            "const DESKTOP_UPDATES_ENABLED = true;"),
                           encoding="utf-8")
        self.assertFalse(next(x["passed"] for x in source_audit(self.root)["checks"]
                              if x["name"] == "updater_runtime_disabled"))

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
        self.assertIn("EBBot-windows-installer-v3.21.0.exe",
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

    def test_tampered_installer_bytes_fail_sha512_validation(self):
        self._create_sample_package()
        installer = self.dist / "EBBot-windows-installer-v3.21.0.exe"
        installer.write_bytes(installer.read_bytes() + b"tampering")
        result = package_audit(self.root, self.dist, "3.21.0")
        self.assertEqual(result["package_validation"], "FAILED")
        metadata_check = next(x for x in result["checks"] if x["name"] == "updater_metadata")
        self.assertFalse(metadata_check["passed"])
        self.assertIn("SHA-512", metadata_check["detail"])

    def test_wrong_base64_checksum_is_rejected(self):
        self._create_sample_package()
        latest = self.dist / "latest.yml"
        latest.write_text(latest.read_text(encoding="utf-8").replace(
            "sha512: ", "sha512: incorrect-", 1
        ), encoding="utf-8")
        self.assertEqual(package_audit(self.root, self.dist, "3.21.0")["package_validation"],
                         "FAILED")

    def test_manifest_rejects_external_url_and_duplicate_asset(self):
        self._create_sample_package()
        latest = self.dist / "latest.yml"
        original = latest.read_text(encoding="utf-8")
        latest.write_text(original.replace(
            "  - url: EBBot-windows-installer-v3.21.0.exe",
            "  - url: https://unapproved.example/installer.exe",
        ), encoding="utf-8")
        self.assertEqual(package_audit(self.root, self.dist, "3.21.0")["package_validation"],
                         "FAILED")
        latest.write_text(original.replace(
            "path: EBBot-windows-installer-v3.21.0.exe",
            "  - url: EBBot-windows-installer-v3.21.0.exe\n"
            "path: EBBot-windows-installer-v3.21.0.exe",
        ), encoding="utf-8")
        self.assertEqual(package_audit(self.root, self.dist, "3.21.0")["package_validation"],
                         "FAILED")

    def test_wrong_file_size_and_missing_digest_fail(self):
        self._create_sample_package()
        latest = self.dist / "latest.yml"
        original = latest.read_text(encoding="utf-8")
        latest.write_text(original.replace("    size: 24", "    size: 123456"),
                          encoding="utf-8")
        self.assertEqual(package_audit(self.root, self.dist, "3.21.0")["package_validation"],
                         "FAILED")
        latest.write_text(original.replace("sha512:", "removed_sha512:", 1),
                          encoding="utf-8")
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
