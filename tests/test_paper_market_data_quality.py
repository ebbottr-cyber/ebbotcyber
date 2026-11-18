"""Offline quote-integrity gate tests. No live HTTP, prices or order routes."""
from __future__ import annotations

from datetime import date, datetime, timezone
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout

from src.services.paper_market_data_quality import (
    active_spot_assets, check_bist, check_futures, check_spot,
)
from src.services.paper_universe_sources import (
    BINANCE_SPOT_URL, BINANCE_SPOT_TICKERS_URL,
    USDM_MARKS_URL, COINM_MARKS_URL, fetch_source,
)
from scripts.audit_paper_quote_sources import parser, run


def spot_exchange() -> str:
    return json.dumps({"symbols": [
        {"symbol": "BTCUSDT", "baseAsset": "BTC", "quoteAsset": "USDT",
         "status": "TRADING", "isSpotTradingAllowed": True},
        {"symbol": "ETHUSDT", "baseAsset": "ETH", "quoteAsset": "USDT",
         "status": "TRADING", "isSpotTradingAllowed": True},
        {"symbol": "OLDUSDT", "baseAsset": "OLD", "quoteAsset": "USDT",
         "status": "BREAK", "isSpotTradingAllowed": True},
    ]})


def spot_ticks() -> str:
    return json.dumps([
        {"symbol": "BTCUSDT", "lastPrice": "100.34", "closeTime": 1700000000000},
        {"symbol": "ETHUSDT", "lastPrice": "0", "closeTime": 1700000000000},
    ])


def future_manifest(market: str, active: tuple[str, ...] = ("BTCUSDT",),
                    size: str | None = None) -> str:
    rows = []
    for s in active:
        row = {"market": market, "instrument_kind": "derivative_contract",
               "symbol": s, "contract_type": "PERPETUAL", "active": True}
        if size is not None:
            row["contract_size_unverified"] = size
        rows.append(row)
    return json.dumps({"contracts": rows})


KAP = "market,symbol,source\ntr,THYAO.IS,kap_bist_company_directory\ntr,AKBNK.IS,kap_bist_company_directory\n"


class QuoteQualityTests(unittest.TestCase):
    def test_spot_24h_close_is_not_last_trade_timestamp(self):
        s = check_spot(spot_exchange(), spot_ticks(), {"BTC", "ETH", "USDT"})
        self.assertEqual((s["expected_active_pairs"], s["positive_price_pairs"],
                          s["invalid_price_pairs"]), (2, 1, 1))
        self.assertEqual(s["verified_trade_event_times"], 0)
        self.assertEqual(s["executable_prices"], 0)
        self.assertEqual(s["indicative_quote_review_candidate_count"], 0)
        self.assertEqual(s["quote_review_block_reasons"]["BTCUSDT"], "missing_24h_trade_count")
        self.assertEqual(s["invalid_price_symbols"], ["ETHUSDT"])
        self.assertEqual(s["invalid_price_reasons"], {"ETHUSDT": "nonpositive_last_price"})
        self.assertEqual(s["missing_price_symbols"], [])
        self.assertFalse(s["paper_ready"])

    def test_spot_provider_drift_and_missing_ticker_visible(self):
        ex = check_spot(spot_exchange(), json.dumps([
            {"symbol": "BTCUSDT", "lastPrice": "1.01"}
        ]), {"BTC", "USDT", "OLD"})
        self.assertEqual(ex["missing_pairs"], 1)
        self.assertEqual(ex["missing_price_symbols"], ["ETHUSDT"])
        self.assertEqual(ex["invalid_price_symbols"], [])
        self.assertEqual(ex["saved_assets_not_current"], 1)
        self.assertEqual(ex["current_assets_not_saved"], 1)

    def test_spot_distinguishes_no_recent_trades_from_corrupt_price(self):
        exchange = json.dumps({"symbols": [
            {"symbol": f"ALT{i}USDT", "baseAsset": f"ALT{i}", "quoteAsset": "USDT",
             "status": "TRADING", "isSpotTradingAllowed": True}
            for i in range(5)
        ]})
        tick = json.dumps([
            {"symbol": "ALT0USDT", "lastPrice": "0", "count": 0},
            {"symbol": "ALT1USDT", "lastPrice": "NaN", "count": 5},
            {"symbol": "ALT2USDT", "lastPrice": "10", "count": 0},
            {"symbol": "ALT3USDT", "lastPrice": "-1", "count": 8},
            {"symbol": "ALT4USDT", "lastPrice": "9", "count": -2},
        ])
        result = check_spot(exchange, tick, set())
        self.assertEqual(result["positive_price_pairs"], 1)
        self.assertEqual(result["invalid_price_pairs"], 4)
        self.assertEqual(result["indicative_quote_review_candidate_count"], 0)
        self.assertEqual(result["quote_review_blocked_pair_count"], 5)
        self.assertEqual(result["quote_review_block_reasons"]["ALT2USDT"], "zero_trades_24h")
        self.assertEqual(result["zero_trades_24h_symbols"], ["ALT0USDT", "ALT2USDT"])
        self.assertEqual(result["invalid_price_reasons"], {
            "ALT0USDT": "nonpositive_last_price_no_trades_24h",
            "ALT1USDT": "non_finite_last_price",
            "ALT3USDT": "nonpositive_last_price",
            "ALT4USDT": "invalid_24h_trade_count",
        })
        self.assertFalse(result["paper_ready"])

    def test_positive_price_and_24h_trades_only_allows_quote_review(self):
        data = json.dumps({"symbols": [
            {"symbol": "BTCUSDT", "baseAsset": "BTC", "quoteAsset": "USDT",
             "status": "TRADING", "isSpotTradingAllowed": True},
            {"symbol": "LTCUSDT", "baseAsset": "LTC", "quoteAsset": "USDT",
             "status": "TRADING", "isSpotTradingAllowed": True},
        ]})
        ticks = json.dumps([
            {"symbol": "BTCUSDT", "lastPrice": "123", "count": 9},
            {"symbol": "LTCUSDT", "lastPrice": "12", "count": 0},
        ])
        r = check_spot(data, ticks, set())
        self.assertEqual(r["indicative_quote_review_candidates"], ["BTCUSDT"])
        self.assertEqual(r["quote_review_block_reasons"], {"LTCUSDT": "zero_trades_24h"})
        self.assertEqual(r["executable_prices"], 0)
        self.assertTrue(r["quote_review_needs_fresh_order_book_and_spread"])
        self.assertFalse(r["paper_ready"])

    def test_spot_diagnostic_keeps_every_invalid_symbol_not_top_n(self):
        exchange = json.dumps({"symbols": [
            {"symbol": f"ERR{i:04d}", "baseAsset": "ERR", "quoteAsset": "USD",
             "status": "TRADING", "isSpotTradingAllowed": True}
            for i in range(205)
        ]})
        tick = json.dumps([
            {"symbol": f"ERR{i:04d}", "lastPrice": "0", "count": 0}
            for i in range(205)
        ])
        result = check_spot(exchange, tick, set())
        self.assertEqual(result["invalid_price_pairs"], 205)
        self.assertEqual(len(result["invalid_price_reasons"]), 205)
        self.assertEqual(result["zero_trades_24h_pairs"], 205)
        self.assertEqual(result["quote_review_blocked_pair_count"], 205)
        self.assertEqual(len(result["quote_review_block_reasons"]), 205)
        self.assertEqual(result["positive_price_pairs"], 0)
        self.assertEqual(result["executable_prices"], 0)

    def test_spot_duplicates_and_malformed_response_block(self):
        with self.assertRaisesRegex(ValueError, "spot_24h_duplicate"):
            check_spot(spot_exchange(), json.dumps([
                {"symbol": "BTCUSDT", "lastPrice": "1"},
                {"symbol": "BTCUSDT", "lastPrice": "2"},
            ]), set())
        with self.assertRaisesRegex(ValueError, "spot_24h_invalid_array"):
            check_spot(spot_exchange(), '{"code":-1}', set())

    def test_spot_snapshot_active_inventory_read_only(self):
        data = json.dumps({"assets": [
            {"network": "binance_spot_catalog", "symbol": "BTC", "active": True},
            {"network": "binance_spot_catalog", "symbol": "ZZZ", "active": False},
        ]})
        self.assertEqual(active_spot_assets(data), {"BTC"})

    def test_futures_provider_mark_time_and_staleness(self):
        now = 1700000000000
        manifest = future_manifest("binance_usdm_futures",
                                   ("AUSDT", "BUSDT", "CUSDT", "DUSDT"))
        marks = json.dumps([
            {"symbol": "AUSDT", "markPrice": "10", "time": now - 1000},
            {"symbol": "BUSDT", "markPrice": "12", "time": now - 300000},
            {"symbol": "CUSDT", "markPrice": "NaN", "time": now - 1000},
        ])
        result = check_futures(manifest, marks, market="binance_usdm_futures", now_ms=now)
        self.assertEqual((result["fresh_mark_count"], result["stale_mark_count"],
                          result["invalid_mark_count"], result["missing_mark_count"]), (1, 1, 1, 1))
        self.assertFalse(result["funding_and_liquidation_model_verified"])
        self.assertEqual(result["executable_prices"], 0)

    def test_futures_future_timestamp_rejected_and_coinm_size_visible(self):
        now = 1700000000000
        data = future_manifest("binance_coinm_futures", ("BTCUSD_PERP",))
        mark = json.dumps([{"symbol": "BTCUSD_PERP", "markPrice": "1200",
                            "time": now + 400000}])
        result = check_futures(data, mark, market="binance_coinm_futures", now_ms=now)
        self.assertEqual(result["stale_mark_count"], 1)
        self.assertEqual(result["coinm_missing_contract_size"], 1)

    def test_futures_untrusted_duplicate_mark_blocks(self):
        marks = json.dumps([
            {"symbol": "BTCUSDT", "markPrice": "1", "time": 1700000000000},
            {"symbol": "BTCUSDT", "markPrice": "2", "time": 1700000000000},
        ])
        with self.assertRaisesRegex(ValueError, "futures_marks_duplicate"):
            check_futures(future_manifest("binance_usdm_futures"), marks,
                          market="binance_usdm_futures", now_ms=1700000000000)

    def test_bist_without_licensed_bars_is_missing_not_fabricated(self):
        result = check_bist(KAP, None, today=date(2026, 11, 18))
        self.assertEqual(result["bist_company_code_candidates"], 2)
        self.assertEqual(result["missing_close"], 2)
        self.assertFalse(result["daily_bars_supplied"])
        self.assertFalse(result["paper_ready"])

    def test_bist_daily_is_indicative_not_intraday(self):
        data = ("symbol,close,as_of,source,currency\n"
                "THYAO.IS,280.30,2026-11-17,licensed_daily,TRY\n"
                "AKBNK.IS,0,2026-11-17,licensed_daily,TRY\n")
        result = check_bist(KAP, data, today=date(2026, 11, 18))
        self.assertEqual((result["recent_daily_close"], result["invalid_close"]), (1, 1))
        self.assertEqual(result["intraday_fresh_quotes"], 0)
        self.assertFalse(result["market_listing_verified"])

    def test_bist_no_stale_or_future_daily_close_silently_counted(self):
        data = ("symbol,close,as_of,source,currency\n"
                "THYAO.IS,280.30,2026-09-01,licensed_daily,TRY\n"
                "AKBNK.IS,70.00,2027-01-01,licensed_daily,TRY\n")
        result = check_bist(KAP, data, today=date(2026, 11, 18))
        self.assertEqual(result["stale_close"], 2)
        self.assertEqual(result["recent_daily_close"], 0)

    def test_public_allowlist_excludes_orders(self):
        for url in ("https://fapi.binance.com/fapi/v1/order",
                    "https://data-api.binance.vision/api/v3/order"):
            with self.assertRaisesRegex(ValueError, "unapproved_inventory_source"):
                fetch_source(url)

    def test_cli_off_by_default_does_not_read_files_or_connect(self):
        args = parser().parse_args(["--stocks", "not-found.csv", "--spot", "none.json",
                                    "--usdm", "none2.json", "--coinm", "none3.json"])
        with patch("scripts.audit_paper_quote_sources.fetch_source",
                   side_effect=AssertionError("network")):
            self.assertEqual(run(args), 0)

    def test_cli_four_public_gets_quality_report_without_writes(self):
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "kap.csv").write_text(KAP, encoding="utf-8")
            (root / "spot.json").write_text(json.dumps({"assets": [
                {"network": "binance_spot_catalog", "symbol": "BTC", "active": True},
                {"network": "binance_spot_catalog", "symbol": "ETH", "active": True},
                {"network": "binance_spot_catalog", "symbol": "USDT", "active": True},
            ]}), encoding="utf-8")
            (root / "usdm.json").write_text(future_manifest("binance_usdm_futures"), encoding="utf-8")
            (root / "coinm.json").write_text(
                future_manifest("binance_coinm_futures", ("BTCUSD_PERP",), "100"),
                encoding="utf-8")
            args = parser().parse_args([
                "--fetch", "--stocks", str(root / "kap.csv"), "--spot", str(root / "spot.json"),
                "--usdm", str(root / "usdm.json"), "--coinm", str(root / "coinm.json"),
            ])
            responses = {
                BINANCE_SPOT_URL: spot_exchange(),
                BINANCE_SPOT_TICKERS_URL: spot_ticks(),
                USDM_MARKS_URL: json.dumps([{
                    "symbol": "BTCUSDT", "markPrice": "100", "time": now_ms
                }]),
                COINM_MARKS_URL: json.dumps([{
                    "symbol": "BTCUSD_PERP", "markPrice": "100", "time": now_ms
                }]),
            }
            called: list[str] = []
            def fake(url: str) -> str:
                called.append(url)
                return responses[url]
            output = StringIO()
            with patch("scripts.audit_paper_quote_sources.fetch_source", side_effect=fake):
                with redirect_stdout(output):
                    self.assertEqual(run(args), 0)
            report = json.loads(output.getvalue())
            self.assertEqual(len(called), 4)
            self.assertEqual(report["bist"]["missing_close"], 2)
            self.assertEqual(report["usdm"]["fresh_mark_count"], 1)
            self.assertEqual(report["coinm"]["fresh_mark_count"], 1)
            self.assertEqual(report["orders"], 0)
            self.assertEqual(report["journal_writes"], 0)
            self.assertEqual(len(list(root.iterdir())), 4)


if __name__ == "__main__":
    unittest.main()
