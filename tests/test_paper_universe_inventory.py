"""No external APIs and no three-symbol pilot cap."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from src.services.paper_universe_inventory import audit_universe

INDEX = Path(__file__).resolve().parents[1] / "apps/dsa-web/public/stocks.index.json"


class PaperUniverseTests(unittest.TestCase):
    def test_all_existing_stocks_not_samples(self):
        result = audit_universe(INDEX)
        self.assertGreaterEqual(result["stock_count"], 30000)
        self.assertEqual(result["stock_count"], sum(result["stocks_by_market"].values()))
        self.assertEqual(result["coin_count"], 0)
        self.assertIn("bist_inventory_missing", result["missing_source_inventories"])
        self.assertIn("coin_inventory_missing", result["missing_source_inventories"])
        self.assertFalse(result["fixed_top_n_cap"])
        self.assertFalse(result["paper_trading_enabled"])
        self.assertFalse(result["live_trading_enabled"])

    def test_501_bist_stocks_and_601_coins_without_clipping(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            st = root / "bist.csv"
            st.write_text("market,symbol,source,kind\n" + "".join(
                f"tr,TEST{i:05d}.IS,operator_market_snapshot,stock\n" for i in range(501)
            ), encoding="utf-8")
            co = root / "coins.jsonl"
            co.write_text("".join(json.dumps({
                "network": "solana", "asset_id": f"test-asset-{i}",
                "symbol": f"C{i}", "source": "operator_provider_snapshot"
            }) + "\n" for i in range(601)), encoding="utf-8")
            result = audit_universe(INDEX, stock_manifests=[st], coin_manifests=[co])
            self.assertEqual(result["stocks_by_market"]["tr"], 501)
            self.assertEqual(result["coins_by_network"]["solana"], 601)
            self.assertEqual(result["instrument_count"], result["stock_count"] + 601)
            self.assertEqual(result["network_requests"], 0)
            self.assertEqual(result["orders"], 0)
            self.assertEqual(result["journal_writes"], 0)

    def test_multiple_crypto_networks_no_duplicate_count_inflation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "crypto.json"
            path.write_text(json.dumps({"assets": [
                {"network": "ethereum", "asset_id": "0xABC", "symbol": "X", "source": "provider"},
                {"network": "ethereum", "asset_id": "0xabc", "symbol": "X", "source": "provider"},
                {"network": "solana", "asset_id": "ABC", "symbol": "X", "source": "provider"},
                {"network": "bitcoin", "asset_id": "coingecko:bitcoin", "symbol": "BTC", "source": "provider"},
            ]}), encoding="utf-8")
            result = audit_universe(INDEX, coin_manifests=[path])
            self.assertEqual(result["coin_count"], 3)
            self.assertEqual(result["duplicates_deduplicated"], 1)

    def test_spot_coins_and_futures_contracts_are_never_combined(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            spot = root / "spot.json"
            future = root / "future.json"
            spot.write_text(json.dumps({"assets": [
                {"network": "binance_spot_catalog", "asset_id": "binance:asset:abc",
                 "symbol": "BTC", "source": "binance_spot_exchange_info"}
            ]}), encoding="utf-8")
            future.write_text(json.dumps({"contracts": [
                {"market": "binance_usdm_futures", "asset_id": "futures:123",
                 "instrument_kind": "derivative_contract", "symbol": "BTCUSDT",
                 "contract_symbol": "BTCUSDT", "contract_type": "PERPETUAL",
                 "base_asset": "BTC", "quote_asset": "USDT", "margin_asset": "USDT",
                 "source": "binance_usdm_exchange_info", "contract_status": "TRADING",
                 "active": True}
            ]}), encoding="utf-8")
            result = audit_universe(INDEX, coin_manifests=[spot], contract_manifests=[future])
            self.assertEqual(result["coin_count"], 1)
            self.assertEqual(result["futures_contract_count"], 1)
            self.assertEqual(result["futures_contracts_by_market"]["binance_usdm_futures"], 1)
            self.assertEqual(result["instrument_count"], result["stock_count"] + 2)
            self.assertFalse(result["leverage_enabled"])
            self.assertFalse(result["paper_trading_enabled"])

    def test_invalid_coin_record_blocks_entire_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad.jsonl"
            path.write_text('{"network":"solana","asset_id":"ABC"}\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid_coin_symbol"):
                audit_universe(INDEX, coin_manifests=[path])

    def test_invalid_stock_symbol_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "stocks.csv"
            path.write_text("market,symbol,source\ntr,../broken,provider\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid_stock_symbol"):
                audit_universe(INDEX, stock_manifests=[path])


if __name__ == "__main__":
    unittest.main()
