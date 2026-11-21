"""Synthetic fail-closed NSIS contract mutation tests; NO installer is run."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audit_ebbot_nsis_upgrade_contract.py"
SPEC = importlib.util.spec_from_file_location("ebbot_nsis_upgrade_contract", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class EBBotNsisUpgradeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.installer = (ROOT / MODULE.INSTALLER).read_text(encoding="utf-8")
        cls.package = json.loads((ROOT / MODULE.PACKAGE).read_text(encoding="utf-8"))
        cls.desktop_main = (ROOT / MODULE.MAIN).read_text(encoding="utf-8")
        cls.workflow = (ROOT / MODULE.WORKFLOW).read_text(encoding="utf-8")

    def check_sources(self, installer=None, package=None, desktop_main=None, workflow=None):
        return MODULE.audit(
            self.installer if installer is None else installer,
            deepcopy(self.package if package is None else package),
            self.desktop_main if desktop_main is None else desktop_main,
            self.workflow if workflow is None else workflow,
        )

    def assert_refused(self, expected, **sources):
        result = self.check_sources(**sources)
        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        self.assertIn(expected, result["failed_checks"])
        self.assertEqual(result["release_status"], "BLOCKED")
        self.assertFalse(result["ready_to_publish"])
        self.assertFalse(result["installer_executed"])
        self.assertFalse(result["upgrade_performed"])
        self.assertFalse(result["user_files_accessed"])

    def test_real_repo_contract_passes_but_release_remains_blocked(self):
        result = self.check_sources()
        self.assertEqual(result["status"], "PASSED_SOURCE_ONLY", result["failed_checks"])
        self.assertEqual(len(result["checks"]), 8)
        self.assertTrue(all(result["checks"].values()))
        self.assertEqual(result["release_status"], "BLOCKED")
        self.assertFalse(result["ready_to_publish"])
        self.assertFalse(result["automatic_updates_enabled"])

    def test_missing_old_uninstaller_keep_app_data_refused(self):
        self.assert_refused("quoted_retry_preserves_app_data",
            installer=self.installer.replace("/S /KEEP_APP_DATA", "/S", 1))

    def test_malformed_quoted_install_dir_refused(self):
        self.assert_refused("quoted_retry_preserves_app_data",
            installer=self.installer.replace('"_?=$R8"', "_?=$R8", 1))

    def test_old_uninstaller_failure_does_not_become_success(self):
        self.assert_refused("old_uninstaller_nonzero_fails_closed",
            installer=self.installer.replace("SetErrorLevel 2", "SetErrorLevel 0"))

    def test_removed_uninstaller_quit_refused(self):
        self.assert_refused("old_uninstaller_nonzero_fails_closed",
            installer=self.installer.replace("  Quit", "  Return"))

    def test_installer_no_longer_forces_per_user_is_refused(self):
        self.assert_refused("per_user_install_only",
            installer=self.installer.replace("StrCpy $isForceCurrentInstall 1",
                                            "StrCpy $isForceCurrentInstall 0"))

    def test_deletion_command_introduced_is_refused(self):
        self.assert_refused("no_custom_data_deletion_commands",
            installer=self.installer + "\nRMDir /r '$INSTDIR\\\\data'\n")

    def test_no_protected_directory_guard_is_refused(self):
        self.assert_refused("explicit_safe_install_directory",
            installer=self.installer.replace("Function .onVerifyInstDir",
                                            "Function .onAllowAnyInstDir"))

    def test_elevated_install_is_refused(self):
        package = deepcopy(self.package)
        package["build"]["nsis"]["allowElevation"] = True
        self.assert_refused("package_per_user_nsis_constraints", package=package)

    def test_wrong_product_identity_is_refused(self):
        package = deepcopy(self.package)
        package["build"]["productName"] = "Other App"
        self.assert_refused("package_per_user_nsis_constraints", package=package)

    def test_auto_update_enabled_is_refused(self):
        self.assert_refused("desktop_auto_update_hard_disabled",
            desktop_main=self.desktop_main.replace(
                "const DESKTOP_UPDATES_ENABLED = false;",
                "const DESKTOP_UPDATES_ENABLED = true;",
            ))

    def test_publish_switch_without_never_is_refused(self):
        self.assert_refused("ci_package_never_published",
            workflow=self.workflow.replace("--win nsis --publish never",
                                           "--win nsis --publish always"))

    def test_ci_permission_escalation_is_refused(self):
        self.assert_refused("ci_package_never_published",
            workflow=self.workflow.replace("permissions:\n  contents: read",
                                           "permissions:\n  contents: write"))

    def test_script_is_read_only_and_never_executes_installer(self):
        # The source checker accepts plain strings and a JSON object, without
        # importing Node, PyInstaller, NSIS, Windows registry or user profile.
        initial = (self.installer, self.desktop_main, self.workflow,
                   json.dumps(self.package, sort_keys=True))
        result = self.check_sources()
        final = (self.installer, self.desktop_main, self.workflow,
                 json.dumps(self.package, sort_keys=True))
        self.assertEqual(initial, final)
        self.assertFalse(result["installer_executed"])
        self.assertFalse(result["upgrade_performed"])


if __name__ == "__main__":
    unittest.main()
