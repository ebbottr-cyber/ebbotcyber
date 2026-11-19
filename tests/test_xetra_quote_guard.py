"""Offline contract tests for fail-closed Xetra quote verification."""
from __future__ import annotations

from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from scripts.verify_xetra_quotes import parser, run
from src.services.xetra_quote_guard import (
    MAX_SYMBOLS, assess_chart_metadata, check_symbols,
    fetch_yahoo_chart, read_xetra_manifest,
)

NOW = datetime(2026, 11, 18, 20, 0, tzinfo=timezone.utc)
HEADER = "market,symbol,source,kind,source_as_of_date,isin,price_symbol_verified\n"
SAP = "de,SAP.DE,deutsche_boerse_xetra_t7,stock,2026-11-18,DE0007164600,false\n"
SIE = "de,SIE.DE,deutsche_boerse_xetra_t7,stock,2026-11-18,DE0007236101,false\n"


def chart(symbol="SAP.DE", **overrides):
    meta = {
        "symbol": symbol, "currency": "EUR",
        "instrumentType": "EQUITY", "fullExchangeName": "XETRA",
        "exchangeName": "GER", "exchangeTimezoneName": "Europe/Berlin",
        "regularMarketPrice": 190.25,
        "regularMarketTime": int((NOW - timedelta(hours=2)).timestamp()),
    }
    meta.update(overrides)
    return {"chart": {"error": None, "result": [{"meta": meta}]}}


class XetraQuoteGuardTests(unittest.TestCase):
    def test_manifest_reads_exact_official_candidates(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "xetra.csv"
            path.write_text(HEADER + SAP + SIE, encoding="utf-8")
            rows = read_xetra_manifest(path)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows["SAP.DE"]["isin"], "DE0007164600")

    def test_official_19_nov_1750_candidate_manifest_includes_new_mnemonic(self):
        path = Path(__file__).resolve().parents[1] / (
            "data/market_snapshots/de/xetra-candidates.csv"
        )
        manifest = read_xetra_manifest(path)
        self.assertEqual(len(manifest), 1750)
        self.assertEqual(manifest["1ANT.DE"]["isin"], "US03703U1079")
        self.assertEqual(manifest["1ANT.DE"]["source_as_of_date"], "2026-11-19")
        fetch = Mock(return_value=chart(symbol="1ANT.DE"))
        report = check_symbols(manifest, ["1ANT.DE"], fetch, now=NOW)
        self.assertEqual(report["candidate_count_in_manifest"], 1750)
        self.assertEqual(report["quote_metadata_matches"], 1)
        self.assertEqual(report["checks"][0]["candidate_isin"], "US03703U1079")
        self.assertFalse(report["checks"][0]["isin_identity_verified"])
        self.assertFalse(report["checks"][0]["real_time_price_verified"])
        self.assertFalse(report["paper_trading_enabled"])
        self.assertFalse(report["live_trading_enabled"])
        self.assertEqual(report["orders"], 0)
        fetch.assert_called_once_with("1ANT.DE")

    def test_manifest_rejects_non_xetra_and_false_claims(self):
        invalid = (
            HEADER + SAP.replace(",stock,", ",etf,"),
            HEADER + SAP.replace(",false", ",true"),
            HEADER + SAP + SAP,
            HEADER + SAP.replace(",deutsche_boerse_xetra_t7,", ",untrusted,"),
            HEADER + SAP.replace("DE0007164600", "not_an_isin"),
        )
        for csv_input in invalid:
            with self.subTest(csv_input=csv_input[-100:]):
                with tempfile.TemporaryDirectory() as folder:
                    path = Path(folder) / "bad.csv"
                    path.write_text(csv_input, encoding="utf-8")
                    with self.assertRaises(ValueError):
                        read_xetra_manifest(path)

    def test_match_is_only_metadata_not_real_time_or_isin(self):
        result = assess_chart_metadata("SAP.DE", chart(), now=NOW)
        self.assertEqual(result["status"], "QUOTE_METADATA_MATCH")
        self.assertEqual(result["provider_currency"], "EUR")
        self.assertTrue(result["quote_metadata_matched"])
        self.assertFalse(result["isin_identity_verified"])
        self.assertFalse(result["broker_access_verified"])
        self.assertFalse(result["real_time_price_verified"])
        self.assertEqual(result["orders"], 0)

    def test_wrong_market_currency_instrument_time_or_price_blocks(self):
        scenarios = [
            {"symbol": "SAP.F"},
            {"currency": "USD"},
            {"instrumentType": "ETF"},
            {"fullExchangeName": "Frankfurt"},
            {"exchangeTimezoneName": "America/New_York"},
            {"regularMarketPrice": 0},
            {"regularMarketPrice": float("nan")},
            {"regularMarketPrice": True},
            {"regularMarketTime": int((NOW - timedelta(days=9)).timestamp())},
            {"regularMarketTime": int((NOW + timedelta(days=2)).timestamp())},
            {"regularMarketTime": "not-a-timestamp"},
        ]
        for modifications in scenarios:
            with self.subTest(modifications=modifications):
                result = assess_chart_metadata("SAP.DE", chart(**modifications), now=NOW)
                self.assertEqual(result["status"], "BLOCKED")
                self.assertFalse(result["quote_metadata_matched"])
                self.assertEqual(result["orders"], 0)

    def test_malformed_provider_results_block(self):
        for payload in ({}, None, {"chart": {"error": {"code": "404"}, "result": []}},
                        {"chart": {"error": None, "result": []}}):
            with self.subTest(payload=payload):
                self.assertEqual(
                    assess_chart_metadata("SAP.DE", payload, now=NOW)["status"],
                    "BLOCKED",
                )

    def test_only_official_manifest_symbols_queried(self):
        manifest = {"SAP.DE": {"isin": "DE0007164600", "source_as_of_date": "2026-11-18"}}
        fetch = Mock(return_value=chart())
        with self.assertRaisesRegex(ValueError, "symbol_not_in_official"):
            check_symbols(manifest, ["UNKNOWN.DE"], fetch, now=NOW)
        fetch.assert_not_called()
        with self.assertRaisesRegex(ValueError, "symbols_must_be_unique"):
            check_symbols(manifest, ["SAP.DE", "SAP.DE"], fetch, now=NOW)
        with self.assertRaisesRegex(ValueError, "symbols_must_be_unique"):
            check_symbols(manifest, ["SAP.DE"] * (MAX_SYMBOLS + 1), fetch, now=NOW)
        fetch.assert_not_called()

    def test_network_error_is_fail_closed_and_isin_not_verified(self):
        manifest = {"SAP.DE": {"isin": "DE0007164600", "source_as_of_date": "2026-11-18"},
                    "SIE.DE": {"isin": "DE0007236101", "source_as_of_date": "2026-11-18"}}
        def provider(symbol):
            if symbol == "SIE.DE":
                raise TimeoutError("provider not available")
            return chart(symbol)
        result = check_symbols(manifest, ["SAP.DE", "SIE.DE"], provider, now=NOW)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["quote_metadata_matches"], 1)
        self.assertEqual(result["checks"][1]["reason"], "provider_request_failed")
        self.assertFalse(result["all_market_prices_verified"])
        self.assertEqual(result["orders"], 0)

    def test_manual_cli_disabled_does_not_open_network(self):
        stdout = StringIO()
        with patch("scripts.verify_xetra_quotes.fetch_yahoo_chart") as fetch, redirect_stdout(stdout):
            result = run(parser().parse_args(["--symbol", "SAP.DE"]))
        self.assertEqual(result, 0)
        self.assertEqual(json.loads(stdout.getvalue())["status"], "DISABLED")
        fetch.assert_not_called()

    def test_cli_mocked_opt_in_and_exclusive_report(self):
        with tempfile.TemporaryDirectory() as folder:
            csv_path = Path(folder) / "xetra.csv"
            out_path = Path(folder) / "review.json"
            fresh_sap = SAP.replace("2026-11-18", datetime.now(timezone.utc).date().isoformat())
            csv_path.write_text(HEADER + fresh_sap, encoding="utf-8")
            args = parser().parse_args([
                "--fetch", "--symbol", "SAP.DE", "--manifest", str(csv_path),
                "--output", str(out_path),
            ])
            with patch("scripts.verify_xetra_quotes.fetch_yahoo_chart") as fetch:
                fetch.return_value = chart(regularMarketTime=int(datetime.now(timezone.utc).timestamp()))
                with redirect_stdout(StringIO()):
                    code = run(args)
                self.assertEqual(code, 0)
                self.assertTrue(out_path.is_file())
                self.assertEqual(json.loads(out_path.read_text())["quote_metadata_matches"], 1)
                # Never overwrite a previous evidence report.
                with redirect_stdout(StringIO()):
                    again = run(args)
                self.assertEqual(again, 1)
                self.assertEqual(fetch.call_count, 1)

    def test_manual_cli_stale_or_mixed_snapshot_never_fetches(self):
        fresh = datetime.now(timezone.utc).date().isoformat()
        stale = "2026-01-01"
        scenarios = (
            HEADER + SAP.replace("2026-11-18", stale),
            HEADER + SAP.replace("2026-11-18", fresh)
            + SIE.replace("2026-11-18", stale),
        )
        for text in scenarios:
            with self.subTest(rows=text[-100:]):
                with tempfile.TemporaryDirectory() as folder:
                    csv_path = Path(folder) / "xetra.csv"
                    csv_path.write_text(text, encoding="utf-8")
                    args = parser().parse_args([
                        "--fetch", "--symbol", "SAP.DE",
                        "--manifest", str(csv_path),
                    ])
                    with patch("scripts.verify_xetra_quotes.fetch_yahoo_chart") as fetch:
                        with redirect_stdout(StringIO()):
                            code = run(args)
                    self.assertEqual(code, 1)
                    fetch.assert_not_called()

    def test_fetch_url_is_fixed_https_and_get_only(self):
        class Response:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self, amount): return b'{"chart":{"result":[]}}'
        with patch("src.services.xetra_quote_guard.urlopen", return_value=Response()) as open_url:
            self.assertEqual(fetch_yahoo_chart("SAP.DE")["chart"]["result"], [])
            req = open_url.call_args.args[0]
            self.assertEqual(req.get_method(), "GET")
            self.assertTrue(req.full_url.startswith(
                "https://query1.finance.yahoo.com/v8/finance/chart/SAP.DE?"))
        with self.assertRaisesRegex(ValueError, "invalid_xetra_symbol"):
            fetch_yahoo_chart("https://example.com/")
        self.assertEqual(open_url.call_count, 1)


if __name__ == "__main__":
    unittest.main()
