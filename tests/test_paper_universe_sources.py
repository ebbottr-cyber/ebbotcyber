"""Binance Spot + KAP import tests: fixtures only, never use live network."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.refresh_paper_universe_sources import parser, run
from src.services.paper_universe_sources import (
    BINANCE_SPOT_URL, binance_spot_to_json, fetch_source, kap_bist_to_csv,
)
from src.services.paper_universe_inventory import audit_universe

INDEX = Path(__file__).resolve().parents[1] / "apps/dsa-web/public/stocks.index.json"


def pair(base: str, quote: str, *, status: str = "TRADING", spot: bool = True) -> dict:
    return {
        "symbol": base + quote,
        "baseAsset": base,
        "quoteAsset": quote,
        "status": status,
        "isSpotTradingAllowed": spot,
        "permissionSets": [["SPOT"]],
    }


class ManualSourceTests(unittest.TestCase):
    KAP_HTML = (
        "<html><body><h1>BIST Şirketleri</h1>"
        "<table><tr><th>Kod</th><th>Şirket Ünvanı</th><th>Şehir</th></tr>"
        "<tr><td>THYAO</td><td>Türk Hava Yolları A.Ş.</td><td>İstanbul</td></tr>"
        "<tr><td>AKBNK</td><td>Akbank</td><td>İstanbul</td></tr>"
        "<tr><td>BLS BLSMD</td><td>Çoklu Kod Şirketi</td><td>İstanbul</td></tr>"
        "</table></body></html>"
    )

    def test_kap_extracts_full_table(self):
        text, n = kap_bist_to_csv(self.KAP_HTML, "2026-11-18T00:00:00+00:00")
        self.assertEqual(n, 4)
        self.assertIn("tr,THYAO.IS,kap_bist_company_directory,stock", text)
        self.assertIn("tr,BLSMD.IS,kap_bist_company_directory,stock", text)

    def test_kap_blocks_unlabelled_page(self):
        with self.assertRaisesRegex(ValueError, "no_verified_kap"):
            kap_bist_to_csv("<table><tr><td>THYAO</td><td>Company</td></tr></table>" * 3, "2026")

    def test_binance_includes_quote_assets_and_deduplicates_pairs(self):
        data = {"symbols": [
            pair("BTC", "USDT"),
            pair("ETH", "USDT"),
            pair("ETH", "BTC", status="BREAK"),
            pair("BNB", "BTC", status="BREAK"),
            pair("SKIP", "USDT", spot=False),
        ]}
        raw, count, active, pairs, trading_pairs = binance_spot_to_json(
            json.dumps(data), "2026-11-18T00:00:00Z"
        )
        assets = {x["symbol"]: x for x in json.loads(raw)["assets"]}
        self.assertEqual((count, active, pairs, trading_pairs), (4, 3, 4, 2))
        self.assertEqual(set(assets), {"BTC", "USDT", "ETH", "BNB"})
        self.assertFalse(assets["BNB"]["active"])
        self.assertEqual(assets["USDT"]["trading_spot_pair_count"], 2)
        self.assertTrue(assets["BTC"]["asset_id"].startswith("binance:asset:"))
        self.assertEqual(assets["BTC"]["network"], "binance_spot_catalog")

    def test_binance_keeps_non_ascii_asset_identifiers_without_address_guessing(self):
        raw, count, active, _, _ = binance_spot_to_json(
            json.dumps({"symbols": [pair("雪", "USDT")]}), "2026"
        )
        self.assertEqual((count, active), (2, 2))
        self.assertIn("雪", raw)
        self.assertIn("binance_spot_catalog", raw)

    def test_malformed_binance_payload_blocks(self):
        with self.assertRaisesRegex(ValueError, "binance_exchange_info_missing_symbols"):
            binance_spot_to_json('{"code": -1}', "2026")
        with self.assertRaisesRegex(ValueError, "invalid_binance_spot_status"):
            row = pair("ETH", "BTC")
            del row["isSpotTradingAllowed"]
            binance_spot_to_json(json.dumps({"symbols": [row]}), "2026")
        with self.assertRaisesRegex(ValueError, "duplicate_binance_pair"):
            binance_spot_to_json(json.dumps({"symbols": [pair("BTC","USDT"), pair("BTC","USDT")]}), "2026")

    def test_offline_by_default_never_calls_network_or_writes(self):
        with tempfile.TemporaryDirectory() as folder:
            args = parser().parse_args(["--output-dir", folder])
            with patch("scripts.refresh_paper_universe_sources.fetch_source",
                       side_effect=AssertionError("network_request")):
                self.assertEqual(run(args), 0)
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_unknown_urls_cannot_be_fetched(self):
        with self.assertRaisesRegex(ValueError, "unapproved_inventory_source"):
            fetch_source("http://127.0.0.1/")

    def test_binance_is_using_public_market_data_host(self):
        self.assertEqual(BINANCE_SPOT_URL, "https://data-api.binance.vision/api/v3/exchangeInfo")

    def test_partial_invalid_response_does_not_write_either_inventory(self):
        with tempfile.TemporaryDirectory() as folder:
            args = parser().parse_args(["--fetch", "--output-dir", folder])
            kap = self.KAP_HTML.replace("</table>", "".join(
                f"<tr><td>C{i:04d}</td><td>Company {i}</td></tr>" for i in range(100)
            ) + "</table>")
            with patch("scripts.refresh_paper_universe_sources.fetch_source",
                       side_effect=lambda url: kap if "kap.org.tr" in url else '{"code":-1}'):
                with self.assertRaisesRegex(ValueError, "binance_exchange_info_missing_symbols"):
                    run(args)
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_501_binance_pairs_no_top_n_limit_and_inventory_compatible(self):
        with tempfile.TemporaryDirectory() as folder:
            args = parser().parse_args(["--fetch", "--source", "binance", "--output-dir", folder])
            response = json.dumps({"symbols": [
                pair(f"ALT{i:04d}", "USDT") for i in range(501)
            ]})
            with patch("scripts.refresh_paper_universe_sources.fetch_source",
                       return_value=response):
                self.assertEqual(run(args), 0)
            path = Path(folder) / "binance-spot-all.json"
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(len(saved["assets"]), 502)
            inventory = audit_universe(INDEX, coin_manifests=[path])
            self.assertEqual(inventory["coin_count"], 502)
            self.assertEqual(inventory["coins_by_network"]["binance_spot_catalog"], 502)
            self.assertEqual(inventory["orders"], 0)
            self.assertFalse(inventory["paper_trading_enabled"])

    def test_existing_snapshot_is_never_overwritten_without_opt_in(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / "binance-spot-all.json"
            out.write_text("already saved", encoding="utf-8")
            args = parser().parse_args(["--fetch", "--source", "binance", "--output-dir", folder])
            with patch("scripts.refresh_paper_universe_sources.fetch_source",
                       side_effect=AssertionError("network_request")):
                with self.assertRaisesRegex(ValueError, "snapshot_already_exists"):
                    run(args)
            self.assertEqual(out.read_text(encoding="utf-8"), "already saved")


if __name__ == "__main__":
    unittest.main()
