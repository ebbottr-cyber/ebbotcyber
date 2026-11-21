"""Deterministic KAP market staging tests; no external APIs or orders."""
from __future__ import annotations

from contextlib import redirect_stdout
from datetime import date
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.audit_ebbot_kap_market_inventory import (
    KAPInputError, inspect, main, official_page,
)

DAY = date(2026, 11, 21)
URL = "https://www.kap.org.tr/tr/Pazarlar"
HEADER = "pazar,kap_kodu,unvan,kaynak_tarihi,isin\n"


class KAPInventoryTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.csv = self.root / "kap.csv"

    def put(self, rows: str):
        self.csv.write_bytes((HEADER + rows).encode("utf-8"))
        return hashlib.sha256(self.csv.read_bytes()).hexdigest()

    def inspect_rows(self, rows: str, **kwargs):
        digest = self.put(rows)
        return inspect(self.csv, digest, URL, DAY, as_of=DAY, **kwargs)

    def test_stages_all_market_segments_without_making_trading_symbols(self):
        result = self.inspect_rows(
            "YILDIZ PAZAR,THYAO,Ornek Yildiz,2026-11-21,\n"
            "ANA PAZAR,ACSEL,Ornek Ana,2026-11-21,\n"
            "ALT PAZAR,ATAGY,Ornek Alt,2026-11-21,\n"
            "YAKIN İZLEME PAZARI,ATEKS,Ornek Yakin,2026-11-21,\n"
            "PİYASA ÖNCESİ İŞLEM PLATFORMU,XXXX,Ornek Oncesi,2026-11-21,\n"
            "YAPILANDIRILMIŞ ÜRÜNLER VE FON PAZARI,YYYY,Ornek Fon,2026-11-21,\n"
            "GİRİŞİM SERMAYESİ PAZARI,ZZZZ,Ornek Girisim Fonu,2026-11-21,\n"
            "EMTİA PAZARI,QQQQ,Ornek Emtia,2026-11-21,\n"
        )
        self.assertEqual(result["status"], "REVIEW_ONLY_UNMAPPED_KAP_CODES")
        self.assertEqual(result["source_rows"], 8)
        self.assertEqual(result["equity_market_candidate_count"], 5)
        self.assertEqual(result["structured_fund_separate_count"], 1)
        self.assertEqual(result["venture_fund_separate_count"], 1)
        self.assertEqual(result["commodity_separate_count"], 1)
        self.assertTrue(result["all_eight_pay_market_segments_present"])
        self.assertNotIn("ZZZZ", result["kap_codes_pending_provider_symbol_mapping"])
        self.assertNotIn("QQQQ", result["kap_codes_pending_provider_symbol_mapping"])
        self.assertEqual(result["markets"]["watch"]["rows"], 1)
        self.assertEqual(result["verified_provider_symbols"], 0)
        self.assertEqual(result["approved_broker_symbols"], 0)
        self.assertEqual(result["verified_ohlcv_bars"], 0)
        self.assertFalse(result["source_origin_independently_verified"])
        self.assertFalse(result["tradeable_bist_universe_verified"])
        self.assertEqual(result["network_requests"], 0)
        self.assertEqual(result["orders"], 0)
        self.assertNotIn("THYAO.IS", result["kap_codes_pending_provider_symbol_mapping"])

    def test_non_equity_segments_never_count_as_stock_candidates(self):
        result = self.inspect_rows(
            "GİRİŞİM SERMAYESİ PAZARI,AAAA,Ornek GS Fonu,2026-11-21,\n"
            "EMTİA PAZARI,BBBB,Ornek Emtia,2026-11-21,\n"
            "YAPILANDIRILMIŞ ÜRÜNLER VE FON PAZARI,CCCC,Ornek BYF,2026-11-21,\n"
        )
        self.assertEqual(result["source_rows"], 3)
        self.assertEqual(result["equity_market_candidate_count"], 0)
        self.assertEqual(result["kap_codes_pending_provider_symbol_mapping"], [])
        self.assertFalse(result["all_eight_pay_market_segments_present"])
        self.assertEqual(result["venture_fund_separate_count"], 1)
        self.assertEqual(result["commodity_separate_count"], 1)
        self.assertFalse(result["tradeable_bist_universe_verified"])

    def test_sha256_pins_exact_bytes_and_rejects_bom(self):
        digest = self.put("ANA PAZAR,ACSEL,Ornek,2026-11-21,\n")
        self.csv.write_bytes(bytes.fromhex("efbbbf") + self.csv.read_bytes())
        with self.assertRaisesRegex(KAPInputError, "source_sha256_mismatch"):
            inspect(self.csv, digest, URL, DAY, as_of=DAY)

    def test_crlf_mutation_cannot_keep_same_digest(self):
        digest = self.put("ANA PAZAR,ACSEL,Ornek,2026-11-21,\n")
        self.csv.write_bytes(self.csv.read_bytes().replace(b"\n", b"\r\n"))
        with self.assertRaisesRegex(KAPInputError, "source_sha256_mismatch"):
            inspect(self.csv, digest, URL, DAY, as_of=DAY)

    def test_cross_market_duplicate_code_rejected(self):
        with self.assertRaisesRegex(KAPInputError, "invalid_or_duplicate_kap_code"):
            self.inspect_rows(
                "YILDIZ PAZAR,THYAO,Ornek,2026-11-21,\n"
                "ANA PAZAR,THYAO,Ornek,2026-11-21,\n"
            )

    def test_unknown_market_is_not_silently_included(self):
        with self.assertRaisesRegex(KAPInputError, "unknown_market"):
            self.inspect_rows("DİĞER PAZAR,THYAO,Ornek,2026-11-21,\n")

    def test_lowercase_or_malformed_codes_rejected(self):
        for code in ("thyao", "THYAO.IS", "=CMD", "FOO BAR", "A"):
            with self.subTest(code=code):
                with self.assertRaisesRegex(KAPInputError, "invalid_or_duplicate_kap_code"):
                    self.inspect_rows(f"YILDIZ PAZAR,{code},Ornek,2026-11-21,\n")

    def test_rejects_mixed_dates_and_future_snapshot(self):
        with self.assertRaisesRegex(KAPInputError, "mixed_source_dates"):
            self.inspect_rows("YILDIZ PAZAR,THYAO,Ornek,2026-11-20,\n")
        digest = self.put("YILDIZ PAZAR,THYAO,Ornek,2026-11-22,\n")
        with self.assertRaisesRegex(KAPInputError, "invalid_manifest_provenance"):
            inspect(self.csv, digest, URL, date(2026, 11, 22), as_of=DAY)

    def test_stale_source_never_appears_fresh(self):
        digest = self.put("YILDIZ PAZAR,THYAO,Ornek,2026-10-01,\n")
        out = inspect(self.csv, digest, URL, date(2026, 10, 1), as_of=DAY)
        self.assertEqual(out["status"], "BLOCKED_STALE_KAP_SNAPSHOT")

    def test_untrusted_or_lookalike_source_url_rejected(self):
        self.assertTrue(official_page(URL))
        self.assertTrue(official_page(URL + "?market=ANA+PAZAR"))
        for fake in ("http://www.kap.org.tr/tr/Pazarlar",
                     "https://kap.org.tr.evil.com/tr/Pazarlar",
                     "https://www.kap.org.tr/tr/bist-sirketler"):
            with self.subTest(fake=fake):
                self.assertFalse(official_page(fake))
                digest = self.put("YILDIZ PAZAR,THYAO,Ornek,2026-11-21,\n")
                with self.assertRaisesRegex(KAPInputError, "invalid_manifest_provenance"):
                    inspect(self.csv, digest, fake, DAY, as_of=DAY)

    def test_isin_is_format_only_not_source_verified(self):
        result = self.inspect_rows("YILDIZ PAZAR,THYAO,Ornek,2026-11-21,TR1234567890\n")
        self.assertEqual(result["rows_with_unverified_isin_format"], 1)
        self.assertFalse(result["source_origin_independently_verified"])
        with self.assertRaisesRegex(KAPInputError, "invalid_isin_format"):
            self.inspect_rows("YILDIZ PAZAR,THYAO,Ornek,2026-11-21,INVALID\n")

    def test_empty_invalid_columns_and_unterminated_row_rejected(self):
        digest = self.put("")
        with self.assertRaisesRegex(KAPInputError, "empty_market_inventory"):
            inspect(self.csv, digest, URL, DAY, as_of=DAY)
        self.csv.write_text("kap_kodu,unvan\nTHYAO,Ornek\n", encoding="utf-8")
        digest = hashlib.sha256(self.csv.read_bytes()).hexdigest()
        with self.assertRaisesRegex(KAPInputError, "invalid_csv_columns"):
            inspect(self.csv, digest, URL, DAY, as_of=DAY)

    def test_symlink_source_fails_closed(self):
        self.put("YILDIZ PAZAR,THYAO,Ornek,2026-11-21,\n")
        link = self.root / "link.csv"
        try:
            link.symlink_to(self.csv)
        except (OSError, NotImplementedError):
            self.skipTest("No symlink support in runner")
        digest = hashlib.sha256(self.csv.read_bytes()).hexdigest()
        with self.assertRaisesRegex(KAPInputError, "missing_unsafe_or_oversized_source"):
            inspect(link, digest, URL, DAY, as_of=DAY)

    def test_cli_strict_never_authorizes_complete_looking_source(self):
        digest = self.put("YILDIZ PAZAR,THYAO,Ornek,2026-11-21,\n")
        report = self.root / "report.json"
        args = ["prog", "--csv", str(self.csv), "--sha256", digest,
                "--source-url", URL, "--snapshot-date", DAY.isoformat(),
                "--as-of", DAY.isoformat(), "--report-json", str(report), "--strict"]
        with patch("sys.argv", args), redirect_stdout(io.StringIO()):
            code = main()
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(report.read_text(encoding="utf-8"))["status"],
                         "REVIEW_ONLY_UNMAPPED_KAP_CODES")
        self.assertFalse(json.loads(report.read_text(encoding="utf-8"))["live_trading_enabled"])
        with patch("sys.argv", args), redirect_stdout(io.StringIO()):
            self.assertEqual(main(), 1)  # never overwrite an existing report

    def test_invalid_company_title_rejected(self):
        with self.assertRaisesRegex(KAPInputError, "invalid_company_title"):
            self.inspect_rows("YILDIZ PAZAR,THYAO,=HYPERLINK,2026-11-21,\n")


if __name__ == "__main__":
    unittest.main()
