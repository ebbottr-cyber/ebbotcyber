"""No live network: source parser, manual opt-in, and fail-closed tests."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.refresh_paper_universe_sources import parser, run
from src.services.paper_universe_sources import (
    coinpaprika_to_json, fetch_source, kap_bist_to_csv,
)


class ManualSourceTests(unittest.TestCase):
    KAP_HTML = (
        "<html><body><h1>BIST Şirketleri</h1>"
        "<table><tr><th>Kod</th><th>Şirket Ünvanı</th><th>Şehir</th></tr>"
        "<tr><td>THYAO</td><td>Türk Hava Yolları A.Ş.</td><td>İstanbul</td></tr>"
        "<tr><td>AKBNK</td><td>Akbank</td><td>İstanbul</td></tr>"
        "<tr><td>BLS BLSMD</td><td>Çoklu Kod Şirketi</td><td>İstanbul</td></tr>"
        "</table></body></html>"
    )

    def test_kap_extracts_full_table_and_multiple_codes(self):
        text, n = kap_bist_to_csv(self.KAP_HTML, "2026-11-18T00:00:00+00:00")
        self.assertEqual(n, 4)
        self.assertIn("tr,THYAO.IS,kap_bist_company_directory,stock", text)
        self.assertIn("tr,BLSMD.IS,kap_bist_company_directory,stock", text)

    def test_kap_rejects_unlabelled_or_blocked_page(self):
        html = "<table><tr><td>THYAO</td><td>Company</td></tr></table>" * 3
        with self.assertRaisesRegex(ValueError, "no_verified_kap"):
            kap_bist_to_csv(html, "2026")

    def test_coinpaprika_retains_all_catalogue_records_with_active_flag(self):
        raw = json.dumps([
            {"id": "btc-bitcoin", "symbol": "BTC", "is_active": True},
            {"id": "xyz-test", "symbol": "XYZ", "is_active": False},
            {"id": "sol-solana", "symbol": "SOL", "is_active": True},
        ])
        result, all_count, active_count = coinpaprika_to_json(raw, "2026-11-18T00:00:00Z")
        output = json.loads(result)
        self.assertEqual((all_count, active_count), (3, 2))
        self.assertEqual(len(output["assets"]), 3)
        self.assertEqual(output["assets"][0]["network"], "coinpaprika_catalog")
        self.assertFalse(output["assets"][1]["active"])

    def test_malformed_or_duplicate_catalog_fails_entire_source(self):
        with self.assertRaisesRegex(ValueError, "duplicate_coinpaprika_id"):
            coinpaprika_to_json(json.dumps([
                {"id": "btc-bitcoin", "symbol": "BTC", "is_active": True},
                {"id": "btc-bitcoin", "symbol": "BTC", "is_active": True},
            ]), "2026")

    def test_offline_by_default_never_calls_network(self):
        with tempfile.TemporaryDirectory() as folder:
            args = parser().parse_args(["--output-dir", folder])
            with patch("scripts.refresh_paper_universe_sources.fetch_source", side_effect=AssertionError("network")):
                self.assertEqual(run(args), 0)
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_unapproved_source_rejected(self):
        with self.assertRaisesRegex(ValueError, "unapproved_inventory_source"):
            fetch_source("http://127.0.0.1/")

    def test_fetch_both_refuses_partially_invalid_catalog_without_writes(self):
        with tempfile.TemporaryDirectory() as folder:
            args = parser().parse_args(["--fetch", "--output-dir", folder])
            fake = lambda url: (
                self.KAP_HTML.replace("</table>", "".join(
                    f"<tr><td>C{i:04d}</td><td>Company {i}</td></tr>" for i in range(100)
                ) + "</table>") if "kap.org.tr" in url else "[]"
            )
            with patch("scripts.refresh_paper_universe_sources.fetch_source", side_effect=fake):
                with self.assertRaisesRegex(ValueError, "empty_coinpaprika_catalog"):
                    run(args)
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_valid_coin_catalog_and_explicit_fetch_output(self):
        with tempfile.TemporaryDirectory() as folder:
            args = parser().parse_args(["--fetch", "--source", "coinpaprika", "--output-dir", folder])
            data = json.dumps([
                {"id": f"coin-{i}", "symbol": f"C{i}", "is_active": True}
                for i in range(1101)
            ])
            with patch("scripts.refresh_paper_universe_sources.fetch_source", return_value=data):
                self.assertEqual(run(args), 0)
            saved = json.loads((Path(folder) / "coinpaprika-all.json").read_text(encoding="utf-8"))
            self.assertEqual(len(saved["assets"]), 1101)


if __name__ == "__main__":
    unittest.main()
