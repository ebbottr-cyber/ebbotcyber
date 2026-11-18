"""Offline regression for the user-selected four equity markets and Xetra."""
from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import tempfile
import unittest

from scripts.audit_four_market_equities import parser, run
from src.services.four_market_equity import (
    MARKETS, audit_four_market_equities, xetra_equities_to_manifest,
)


def xetra(*rows: str, dated: str = "18.11.2026") -> str:
    header = "Product Status;Instrument Status;Instrument;ISIN;Mnemonic;MIC Code;Instrument Type"
    return "\n".join(("Market: XETR", "Date Last Update: " + dated, header, *rows)) + "\n"


SAP = "Active;Active;SAP SE;DE0007164600;SAP;XETR;CS"
DAX_ETF = "Active;Active;DAX ETF;DE0000000001;DAXF;XETR;ETF"
OLD = "Active;PendingDeletion;OLD CO;DE0000000002;OLD;XETR;CS"
OTHER = "Active;Active;OTHER;DE0000000003;OTHER;XFRA;CS"


class FourMarketEquityTests(unittest.TestCase):
    def test_xetra_selects_only_active_common_stocks(self):
        csv_text, audit = xetra_equities_to_manifest(
            xetra(SAP, DAX_ETF, OLD, OTHER), today=date(2026, 11, 18))
        self.assertIn("de,SAP.DE,deutsche_boerse_xetra_t7,stock,2026-11-18,DE0007164600,false", csv_text)
        self.assertNotIn("DAXF.DE", csv_text)
        self.assertEqual(audit["included_common_stocks"], 1)
        self.assertEqual(audit["excluded_non_equity"], 1)
        self.assertEqual(audit["excluded_inactive"], 1)
        self.assertEqual(audit["excluded_other_mic"], 1)
        self.assertFalse(audit["price_symbols_verified"])
        self.assertEqual(audit["network_requests"], 0)

    def test_xetra_stale_and_future_dates_fail_closed(self):
        for stamp in ("01.11.2026", "19.11.2026"):
            with self.subTest(stamp=stamp):
                with self.assertRaisesRegex(ValueError, "stale_or_future"):
                    xetra_equities_to_manifest(xetra(SAP, dated=stamp), today=date(2026, 11, 18))

    def test_xetra_requires_official_market_header_and_columns(self):
        with self.assertRaisesRegex(ValueError, "wrong_xetra_market"):
            xetra_equities_to_manifest(xetra(SAP).replace("Market: XETR", "Market: XFRA"),
                                       today=date(2026, 11, 18))
        with self.assertRaisesRegex(ValueError, "invalid_xetra_columns"):
            xetra_equities_to_manifest("Market: XETR\nDate Last Update: 18.11.2026\nA;B\n1;2\n",
                                       today=date(2026, 11, 18))

    def test_xetra_rejects_mnemonic_collisions_and_no_equities(self):
        clash = "Active;Active;Other SAP;DE0000000004;SAP;XETR;CS"
        with self.assertRaisesRegex(ValueError, "xetra_mnemonic_collision"):
            xetra_equities_to_manifest(xetra(SAP, clash), today=date(2026, 11, 18))
        with self.assertRaisesRegex(ValueError, "no_active_xetra"):
            xetra_equities_to_manifest(xetra(DAX_ETF), today=date(2026, 11, 18))

    def test_xetra_deduplicates_exact_same_isin(self):
        result, audit = xetra_equities_to_manifest(xetra(SAP, SAP), today=date(2026, 11, 18))
        self.assertEqual(result.count("SAP.DE"), 1)
        self.assertEqual(audit["duplicates_deduplicated"], 1)

    def test_four_markets_include_all_rows_without_top100_and_drop_other_markets(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            idx = root / "stocks.json"
            rows = []
            for i in range(251):
                rows.append([f"A{i}", "", "", "", "", "", "us", "stock", True])
            rows.extend([
                ["0700.HK", "", "", "", "", "", "hk", "stock", True],
                ["7203.T", "", "", "", "", "", "jp", "stock", True],
                ["600519.SS", "", "", "", "", "", "cn", "stock", True],
                ["^GSPC", "", "", "", "", "", "us", "index", True],
            ])
            idx.write_text(json.dumps(rows), encoding="utf-8")
            bist = root / "kap.csv"
            bist.write_text(
                "market,symbol,source,kind\ntr,THYAO.IS,kap_bist_company_directory,stock\n",
                encoding="utf-8")
            xetra_csv = root / "xetra.csv"
            xetra_csv.write_text(
                "market,symbol,source,kind\nde,SAP.DE,deutsche_boerse_xetra_t7,stock\n",
                encoding="utf-8")
            report = audit_four_market_equities(idx, stock_manifests=[bist, xetra_csv])
            self.assertEqual(tuple(report["selected_markets"]), MARKETS)
            self.assertEqual(report["candidate_stocks_by_market"],
                             {"tr": 1, "us": 251, "de": 1, "hk": 1})
            self.assertEqual(report["selected_candidate_stock_count"], 254)
            self.assertEqual(report["out_of_scope_stock_count_excluded"], 2)
            self.assertEqual(report["out_of_scope_markets_excluded"], ["cn", "jp"])
            self.assertEqual(report["index_records_excluded"], 1)
            self.assertFalse(report["fixed_top_n_cap"])
            self.assertFalse(report["full_exchange_coverage_verified"])
            self.assertFalse(report["paper_trading_enabled"])
            self.assertEqual(report["orders"], 0)

    def test_missing_tr_de_is_reported_without_inventing_data(self):
        with tempfile.TemporaryDirectory() as folder:
            index = Path(folder) / "idx.json"
            index.write_text(json.dumps([
                ["AAPL", "", "", "", "", "", "us", "stock", True],
                ["0700.HK", "", "", "", "", "", "hk", "stock", True],
            ]), encoding="utf-8")
            report = audit_four_market_equities(index)
            self.assertEqual(report["status"], "MISSING_MARKET_INVENTORIES")
            self.assertEqual(report["markets_without_candidates"], ["tr", "de"])

    def test_cli_offline_by_default_and_input_pair_required(self):
        args = parser().parse_args(["--xetra-input", "foo.csv"])
        self.assertEqual(run(args), 1)


if __name__ == "__main__":
    unittest.main()
