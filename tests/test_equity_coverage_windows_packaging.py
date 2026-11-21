"""Windows packaging source contract for operator-only coverage endpoint.

This does NOT invoke PyInstaller or launch the installer. The real frozen
Windows import probe runs only during the separately approved package CI.
"""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "scripts" / "build-backend.ps1"
APP = ROOT / "api" / "app.py"
ENDPOINT = ROOT / "api" / "v1" / "endpoints" / "data.py"


class CoverageWindowsSourceContractTests(unittest.TestCase):
    def test_hidden_imports_include_new_router_and_reader(self):
        script = BUILD.read_text(encoding="utf-8")
        imports = script.split("$hiddenImports = @(", 1)[1].split(")", 1)[0]
        self.assertIn("'api.v1.endpoints.data'", imports)
        self.assertIn("'src.services.equity_data_coverage_reader'", imports)
        self.assertIn("'src.services.bist_identity_report_reader'", imports)
        self.assertIn("--hidden-import=", script)

    def test_frozen_import_probe_covers_reader_without_loading_data(self):
        script = BUILD.read_text(encoding="utf-8")
        probes = script.split("Verifying packaged runtime imports...", 1)[1]
        self.assertIn("'src.services.equity_data_coverage_reader'", probes)
        self.assertIn("'src.services.bist_identity_report_reader'", probes)
        self.assertIn("DSA_PACKAGED_IMPORT_PROBE", probes)

    def test_ci_only_frozen_health_probe_never_mounts_real_data_router(self):
        app_source = APP.read_text(encoding="utf-8")
        self.assertIn("if _is_ebbot_packaged_health_probe():", app_source)
        self.assertIn("return app", app_source)
        self.assertIn('app.include_router(api_v1_router, prefix="/api/v1")', app_source)
        self.assertLess(
            app_source.index("if _is_ebbot_packaged_health_probe():", app_source.index("def create_app")),
            app_source.index('app.include_router(api_v1_router, prefix="/api/v1")'),
        )
        probe = (ROOT / "tests" / "test_ebbot_packaged_react_probe.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('"/api/v1/data/equity-coverage"', probe)
        self.assertIn('"/api/v1/data/bist-identity"', probe)

    def test_metadata_endpoint_has_explicit_no_store_and_auth_off_block(self):
        source = ENDPOINT.read_text(encoding="utf-8")
        self.assertIn('response.headers["Cache-Control"] = "no-store"', source)
        self.assertIn("if not is_auth_enabled():", source)
        self.assertIn('unavailable_equity_coverage_report("administrator_auth_required")', source)
        self.assertIn('@router.get(', source)


if __name__ == "__main__":
    unittest.main()
