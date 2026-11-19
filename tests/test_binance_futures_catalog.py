"""USDⓈ-M + COIN-M futures contract inventory tests, mock-only."""
from __future__ import annotations
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.refresh_paper_universe_sources import parser, run
from src.services.binance_futures_catalog import futures_to_json
from src.services.paper_universe_inventory import audit_universe
from src.services.paper_universe_sources import (
    USDM_FUTURES_URL, COINM_FUTURES_URL, fetch_source,
)

INDEX = Path(__file__).resolve().parents[1] / "apps/dsa-web/public/stocks.index.json"


def contract(symbol: str, *, kind: str = "usdm", status: str = "TRADING",
             contract_type: str = "PERPETUAL") -> dict:
    item = {
        "symbol": symbol, "baseAsset": "BTC", "quoteAsset": "USDT" if kind == "usdm" else "USD",
        "marginAsset": "USDT" if kind == "usdm" else "BTC",
        "contractType": contract_type,
    }
    item["status" if kind == "usdm" else "contractStatus"] = status
    if kind == "coinm":
        item["contractSize"] = 100
    return item


class FuturesTests(unittest.TestCase):
    def test_usdm_perpetual_and_delivery_are_distinct(self):
        raw = json.dumps({"symbols": [
            contract("BTCUSDT"),
            contract("ETHUSDT", status="SETTLING"),
            contract("BTCUSDT_261225", contract_type="CURRENT_QUARTER"),
        ]})
        text, total, trading, perps, delivery = futures_to_json(raw, "2026-11-18T00:00:00Z", kind="usdm")
        self.assertEqual((total, trading, perps, delivery), (3, 2, 2, 1))
        rows = json.loads(text)["contracts"]
        self.assertEqual(rows[0]["market"], "binance_usdm_futures")
        self.assertEqual(rows[0]["instrument_kind"], "derivative_contract")
        self.assertFalse(rows[1]["active"])
        self.assertFalse(rows[0]["execution_enabled"])

    def test_coinm_symbol_and_contract_size(self):
        row = contract("BTCUSD_PERP", kind="coinm")
        row["deliveryDate"] = 9999999999999
        text, total, trading, perps, delivery = futures_to_json(
            json.dumps({"symbols": [row]}), "2026", kind="coinm"
        )
        self.assertEqual((total, trading, perps, delivery), (1, 1, 1, 0))
        record = json.loads(text)["contracts"][0]
        self.assertEqual(record["margin_asset"], "BTC")
        self.assertEqual(record["contract_size_unverified"], "100")
        self.assertEqual(record["delivery_date_ms"], 9999999999999)

    def test_printable_unicode_and_punctuation_symbols_preserved(self):
        unusual_symbol = "BTCⓈUSD/26"
        data = json.dumps({"symbols": [contract(unusual_symbol)]})
        text, total, trading, _, _ = futures_to_json(data, "2026", kind="usdm")
        self.assertEqual((total, trading), (1, 1))
        self.assertEqual(json.loads(text)["contracts"][0]["symbol"], unusual_symbol)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "futures.json"
            path.write_text(text, encoding="utf-8")
            result = audit_universe(INDEX, contract_manifests=[path])
            self.assertEqual(result["futures_contract_count"], 1)
            self.assertEqual(result["coin_count"], 0)
            self.assertEqual(result["orders"], 0)

    def test_bad_futures_symbol_reports_source_row_without_dropping(self):
        bad = contract("BTC\nUSDT")
        with self.assertRaisesRegex(ValueError, "invalid_binance_futures_symbol_at_index_0"):
            futures_to_json(json.dumps({"symbols": [bad]}), "2026", kind="usdm")
        bad = contract("  BTCUSDT")
        with self.assertRaisesRegex(ValueError, "invalid_binance_futures_symbol_at_index_0"):
            futures_to_json(json.dumps({"symbols": [bad]}), "2026", kind="usdm")

    def test_no_100_contract_limit(self):
        raw = json.dumps({"symbols": [
            contract(f"ASSET{i:04d}USDT") for i in range(750)
        ]})
        result, total, trading, _, _ = futures_to_json(raw, "2026", kind="usdm")
        self.assertEqual((total, trading), (750, 750))
        self.assertEqual(len(json.loads(result)["contracts"]), 750)

    def test_invalid_and_duplicate_contracts_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "binance_futures_missing_symbols"):
            futures_to_json('{"code":-1}', "2026", kind="usdm")
        with self.assertRaisesRegex(ValueError, "duplicate_binance_futures_symbol"):
            futures_to_json(json.dumps({"symbols": [
                contract("BTCUSDT"), contract("BTCUSDT")
            ]}), "2026", kind="usdm")
        with self.assertRaisesRegex(ValueError, "invalid_binance_futures_contractStatus"):
            futures_to_json(json.dumps({"symbols": [
                contract("BTCUSD_PERP", kind="usdm")
            ]}), "2026", kind="coinm")

    def test_no_credentials_or_order_urls_allowlisted(self):
        self.assertEqual(USDM_FUTURES_URL, "https://fapi.binance.com/fapi/v1/exchangeInfo")
        self.assertEqual(COINM_FUTURES_URL, "https://dapi.binance.com/dapi/v1/exchangeInfo")
        for forbidden in ("https://fapi.binance.com/fapi/v1/order",
                          "https://dapi.binance.com/dapi/v1/order"):
            with self.assertRaisesRegex(ValueError, "unapproved_inventory_source"):
                fetch_source(forbidden)

    def test_no_fetch_no_network_even_when_futures_selected(self):
        with tempfile.TemporaryDirectory() as folder:
            args = parser().parse_args(["--source", "futures", "--output-dir", folder])
            with patch("scripts.refresh_paper_universe_sources.fetch_source",
                       side_effect=AssertionError("called network")):
                self.assertEqual(run(args), 0)
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_both_sources_snapshot_without_automatic_orders(self):
        with tempfile.TemporaryDirectory() as folder:
            args = parser().parse_args(["--fetch", "--source", "futures", "--output-dir", folder])
            def fake(url: str) -> str:
                if url == USDM_FUTURES_URL:
                    return json.dumps({"symbols": [contract("BTCUSDT"), contract("ETHUSDT", status="BREAK")]})
                if url == COINM_FUTURES_URL:
                    return json.dumps({"symbols": [contract("BTCUSD_PERP", kind="coinm")]})
                raise AssertionError("unexpected URL")
            with patch("scripts.refresh_paper_universe_sources.fetch_source", side_effect=fake):
                self.assertEqual(run(args), 0)
            usd = Path(folder) / "binance-usdm-futures.json"
            coin = Path(folder) / "binance-coinm-futures.json"
            result = audit_universe(INDEX, contract_manifests=[usd, coin])
            self.assertEqual(result["coin_count"], 0)
            self.assertEqual(result["futures_contract_count"], 2)
            self.assertEqual(result["futures_contracts_by_market"], {
                "binance_coinm_futures": 1, "binance_usdm_futures": 1,
            })
            self.assertEqual(result["orders"], 0)
            self.assertFalse(result["live_trading_enabled"])

    def test_second_source_failure_no_partial_write(self):
        with tempfile.TemporaryDirectory() as folder:
            args = parser().parse_args(["--fetch", "--source", "futures", "--output-dir", folder])
            with patch("scripts.refresh_paper_universe_sources.fetch_source",
                       side_effect=["""
{"symbols": [{"symbol": "BTCUSDT", "baseAsset": "BTC", "quoteAsset": "USDT",
"marginAsset": "USDT", "contractType": "PERPETUAL", "status": "TRADING"}]}
""", '{"code":-1}']):
                with self.assertRaisesRegex(ValueError, "binance_futures_missing_symbols"):
                    run(args)
            self.assertEqual(list(Path(folder).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
