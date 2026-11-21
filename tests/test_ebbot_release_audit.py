"""Offline safety tests for EBBot release gate; no credentials or provider calls."""
import json
import tempfile
import unittest
from pathlib import Path
from scripts.audit_ebbot_release import REQUIRED, audit

class ReleaseAuditTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        for relative in REQUIRED:
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("fixture", encoding="utf-8")
        (self.root / "apps/dsa-web/public/manifest.webmanifest").write_text(
            json.dumps({"id": "/", "scope": "/", "start_url": "/overview", "display": "standalone"}),
            encoding="utf-8")
        (self.root / "api/v1/endpoints/meme_coin.py").write_text(
            '@router.get("/overview")\ndef read(): pass\n', encoding="utf-8")
        (self.root / "src/services/meme_coin_discovery.py").write_text(
            'flag = os.getenv("MEME_COIN_DISCOVERY_ENABLED", "false")', encoding="utf-8")
        archive = self.root / "workflows_disabled/00-daily-analysis.yml.disabled"
        archive.parent.mkdir(parents=True, exist_ok=True)
        archive.write_text("archived", encoding="utf-8")

    def test_known_safe_snapshot_is_still_not_a_release_approval(self):
        result = audit(self.root)
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["technical_blockers"])
        self.assertEqual(len(result["legacy_contract_reviews"]), 3)
        self.assertEqual(len(result["manual_release_gates"]), 5)
        self.assertFalse(result["enables_live_trading"])

    def test_activating_archived_scheduled_workflow_is_blocked(self):
        path = self.root / ".github/workflows/00-daily-analysis.yml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("on: schedule", encoding="utf-8")
        self.assertTrue(any("reactivated" in x for x in audit(self.root)["technical_blockers"]))

    def test_trade_write_endpoint_is_blocked(self):
        (self.root / "api/v1/endpoints/meme_coin.py").write_text(
            '@router.get("/overview")\n@router.post("/trade")\n', encoding="utf-8")
        self.assertTrue(any("write endpoint" in x for x in audit(self.root)["technical_blockers"]))

    def test_discovery_must_remain_opt_in(self):
        (self.root / "src/services/meme_coin_discovery.py").write_text(
            'flag = os.getenv("MEME_COIN_DISCOVERY_ENABLED", "true")', encoding="utf-8")
        self.assertTrue(any("scanning" in x for x in audit(self.root)["technical_blockers"]))

    def test_missing_asset_and_changed_manifest_are_blocked(self):
        (self.root / "apps/dsa-web/public/sw.js").unlink()
        (self.root / "apps/dsa-web/public/manifest.webmanifest").write_text(
            json.dumps({"start_url": "/"}), encoding="utf-8")
        result = audit(self.root)
        self.assertTrue(any("sw.js" in x for x in result["technical_blockers"]))
        self.assertTrue(any("manifest" in x or "PWA" in x for x in result["technical_blockers"]))

if __name__ == "__main__":
    unittest.main()
