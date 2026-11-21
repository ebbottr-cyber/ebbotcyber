"""Static Windows packaging safety contract for newly added BIST Data Center.

These checks do not perform PyInstaller packaging, code signing, or release.
A separate authorized real Windows installer build remains required.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "scripts" / "build-backend.ps1"
API = ROOT / "api" / "v1" / "endpoints" / "data.py"
PROBE = ROOT / "tests" / "test_ebbot_packaged_react_probe.py"


class BistWindowsPackagingTests(unittest.TestCase):
    def test_bist_reader_hidden_import_is_present_in_backend_packager(self):
        source = BUILD.read_text(encoding="utf-8")
        hidden = source.split("$hiddenImports = @(", 1)[1].split(")", 1)[0]
        self.assertIn("'src.services.bist_identity_report_reader'", hidden)
        self.assertIn("'src.services.equity_data_coverage_reader'", hidden)
        self.assertIn("'api.v1.endpoints.data'", hidden)
        self.assertIn("$hiddenImportArgs", source)
        self.assertIn("'main.py'", source)

    def test_runtime_probe_runs_bist_reader_import_in_frozen_binary(self):
        source = BUILD.read_text(encoding="utf-8")
        section = source.split("Verifying packaged runtime imports...", 1)[1]
        self.assertIn("'src.services.bist_identity_report_reader'", section)
        self.assertIn("DSA_PACKAGED_IMPORT_PROBE", section)
        self.assertIn("Start-Process", section)
        self.assertIn("$probeProcess.ExitCode -ne 0", section)

    def test_frozen_diagnostic_mode_hides_all_private_market_data_api_routes(self):
        source = PROBE.read_text(encoding="utf-8")
        self.assertIn('"/api/v1/data/equity-coverage"', source)
        self.assertIn('"/api/v1/data/bist-identity"', source)
        self.assertIn('self.assertEqual(client.get(path).status_code, 404, path)', source)

    def test_bist_route_has_no_store_and_admin_auth_off_block(self):
        source = API.read_text(encoding="utf-8")
        route = source.split('"/bist-identity"', 1)[1]
        self.assertIn('def get_bist_identity_summary(response: Response)', route)
        self.assertIn('response.headers["Cache-Control"] = "no-store"', route)
        self.assertIn("if not is_auth_enabled():", route)
        self.assertIn('unavailable_bist_identity_report("administrator_auth_required")', route)
        self.assertNotIn("path: str", route)

    def test_local_operator_data_is_not_bundled_with_windows_package(self):
        source = BUILD.read_text(encoding="utf-8")
        self.assertNotIn("EBBOT_BIST_IDENTITY_REPORT_PATH", source)
        self.assertNotIn("bist-identity-summary.json", source)
        self.assertNotIn("C:\\ApprovedMarketData", source)
        self.assertNotIn("operator_provider_review", source)


if __name__ == "__main__":
    unittest.main()
