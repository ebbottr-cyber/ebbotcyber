"""Offline KAP ↔ BIST declared security identity audit, not permission to trade."""
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

from scripts.audit_ebbot_kap_bist_crosswalk import (
    audit, main, official_bist_url,
)
from scripts.audit_ebbot_kap_market_inventory import KAPInputError

DAY = date(2026, 11, 21)
KAP_HEADER = "pazar,kap_kodu,unvan,kaynak_tarihi,isin\n"
BIST_HEADER = "kap_kodu,bist_islem_kodu,pazar,isin,kaynak_tarihi\n"


class CrosswalkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.kap = self.root / "kap.csv"
        self.bist = self.root / "bist.csv"
        self.kap_sha = self.write_kap(
            "YILDIZ PAZAR,AAAA,Ornek A,2026-11-21,\n"
            "ANA PAZAR,BBBB,Ornek B,2026-11-21,\n"
            "YAPILANDIRILMIŞ ÜRÜNLER VE FON PAZARI,CCCC,Ornek Fon,2026-11-21,\n"
        )

    def write_kap(self, rows: str) -> str:
        self.kap.write_bytes((KAP_HEADER + rows).encode("utf-8"))
        return hashlib.sha256(self.kap.read_bytes()).hexdigest()

    def write_bist(self, rows: str) -> str:
        self.bist.write_bytes((BIST_HEADER + rows).encode("utf-8"))
        return hashlib.sha256(self.bist.read_bytes()).hexdigest()

    def call(self, *, bist=True, date_override=None):
        return audit(
            self.kap, self.kap_sha, DAY,
            self.bist if bist else None,
            hashlib.sha256(self.bist.read_bytes()).hexdigest() if bist else None,
            date_override or DAY if bist else None,
            as_of=DAY,
        )

    def test_no_listing_file_does_not_invent_any_market_symbols(self):
        result = self.call(bist=False)
        self.assertEqual(result["declared_bist_instrument_codes"], 0)
        self.assertEqual(result["kap_codes_without_declared_instruments"], 2)
        self.assertEqual(result["kap_codes_without_declared_instruments_full"], ["AAAA", "BBBB"])
        self.assertFalse(result["provider_mapping_verified"])
        self.assertFalse(result["broker_mapping_verified"])
        self.assertFalse(result["official_bist_list_independently_verified"])
        self.assertEqual(result["orders"], 0)

    def test_stages_source_claim_without_verified_provider_or_broker(self):
        self.write_bist(
            "AAAA,ABCDA,YILDIZ PAZAR,TR1111111111,2026-11-21\n"
            "BBBB,EFGHB,ANA PAZAR,TR2222222222,2026-11-21\n"
        )
        report = self.call()
        self.assertEqual(report["declared_bist_instrument_codes"], 2)
        self.assertEqual(report["kap_codes_with_declared_instruments"], 2)
        self.assertEqual(report["kap_codes_without_declared_instruments"], 0)
        self.assertFalse(report["official_bist_list_independently_verified"])
        self.assertFalse(report["isin_independently_verified"])
        self.assertFalse(report["licensed_ohlcv_verified"])
        self.assertFalse(report["live_trading_enabled"])
        self.assertNotIn("ABCDA.IS", report["declared_crosswalk_full"])
        self.assertEqual(report["status"], "BLOCKED_UNVERIFIED_BIST_CROSSWALK")

    def test_multiple_instrument_classes_are_flagged_for_review(self):
        self.write_bist(
            "AAAA,ABCDA,YILDIZ PAZAR,TR1111111111,2026-11-21\n"
            "AAAA,ABCDB,YILDIZ PAZAR,TR2222222222,2026-11-21\n"
        )
        report = self.call()
        self.assertEqual(report["kap_codes_with_declared_instruments"], 1)
        self.assertEqual(report["declared_bist_instrument_codes"], 2)
        self.assertEqual(report["companies_with_multiple_declared_instruments"], ["AAAA"])
        self.assertEqual(report["kap_codes_without_declared_instruments_full"], ["BBBB"])

    def test_same_instrument_symbol_across_companies_rejected(self):
        self.write_bist(
            "AAAA,ABCDA,YILDIZ PAZAR,TR1111111111,2026-11-21\n"
            "BBBB,ABCDA,ANA PAZAR,TR2222222222,2026-11-21\n"
        )
        with self.assertRaisesRegex(KAPInputError, "reused_bist_instrument_code"):
            self.call()

    def test_duplicate_isin_for_two_instruments_rejected(self):
        self.write_bist(
            "AAAA,ABCDA,YILDIZ PAZAR,TR1111111111,2026-11-21\n"
            "BBBB,EFGHB,ANA PAZAR,TR1111111111,2026-11-21\n"
        )
        with self.assertRaisesRegex(KAPInputError, "duplicate_bist_isin"):
            self.call()

    def test_unknown_kap_reference_rejected(self):
        self.write_bist("ZZZZ,QQQQQ,YILDIZ PAZAR,,2026-11-21\n")
        with self.assertRaisesRegex(KAPInputError, "unknown_kap_reference"):
            self.call()

    def test_fund_not_misclassified_as_trading_equity(self):
        self.write_bist("CCCC,FFAFF,YAPILANDIRILMIŞ ÜRÜNLER VE FON PAZARI,,2026-11-21\n")
        with self.assertRaisesRegex(KAPInputError, "non_equity_kap_reference"):
            self.call()

    def test_market_mismatch_rejected(self):
        self.write_bist("AAAA,ABCDA,ANA PAZAR,,2026-11-21\n")
        with self.assertRaisesRegex(KAPInputError, "kap_bist_market_mismatch"):
            self.call()

    def test_kap_isin_mismatch_rejected(self):
        self.kap_sha = self.write_kap(
            "YILDIZ PAZAR,AAAA,Ornek A,2026-11-21,TR1111111111\n"
        )
        self.write_bist("AAAA,ABCDA,YILDIZ PAZAR,TR2222222222,2026-11-21\n")
        with self.assertRaisesRegex(KAPInputError, "kap_bist_isin_mismatch"):
            self.call()

    def test_missing_isin_is_unresolved_not_verified(self):
        self.write_bist("AAAA,ABCDA,YILDIZ PAZAR,,2026-11-21\n")
        result = self.call()
        self.assertEqual(result["instruments_without_isin"], 1)
        self.assertFalse(result["isin_independently_verified"])

    def test_bist_raw_bytes_hash_changes_on_bom(self):
        digest = self.write_bist("AAAA,ABCDA,YILDIZ PAZAR,,2026-11-21\n")
        self.bist.write_bytes(bytes.fromhex("efbbbf") + self.bist.read_bytes())
        with self.assertRaisesRegex(KAPInputError, "sha256_mismatch"):
            audit(self.kap, self.kap_sha, DAY, self.bist, digest, DAY, as_of=DAY)

    def test_bist_raw_bytes_hash_changes_on_newline_mutation(self):
        digest = self.write_bist("AAAA,ABCDA,YILDIZ PAZAR,,2026-11-21\n")
        self.bist.write_bytes(self.bist.read_bytes().replace(b"\n", b"\r\n"))
        with self.assertRaisesRegex(KAPInputError, "sha256_mismatch"):
            audit(self.kap, self.kap_sha, DAY, self.bist, digest, DAY, as_of=DAY)

    def test_future_and_mixed_source_dates_rejected(self):
        self.write_bist("AAAA,ABCDA,YILDIZ PAZAR,,2026-11-20\n")
        with self.assertRaisesRegex(KAPInputError, "mixed_bist_source_dates"):
            self.call()
        with self.assertRaisesRegex(KAPInputError, "untrusted_or_future_bist_source"):
            self.call(date_override=date(2026, 11, 22))

    def test_old_source_remains_blocked(self):
        self.write_bist("AAAA,ABCDA,YILDIZ PAZAR,,2026-11-01\n")
        report = audit(
            self.kap, self.kap_sha, DAY, self.bist,
            hashlib.sha256(self.bist.read_bytes()).hexdigest(),
            date(2026, 11, 1), as_of=DAY,
        )
        self.assertEqual(report["status"], "BLOCKED_STALE_CROSSWALK")

    def test_bist_url_allowlist_is_strict(self):
        self.assertTrue(official_bist_url(
            "https://www.borsaistanbul.com/veriler/pay-piyasasi-verileri"))
        self.write_bist("AAAA,ABCDA,YILDIZ PAZAR,,2026-11-21\n")
        for url in (
            "http://www.borsaistanbul.com/veriler/pay-piyasasi-verileri",
            "https://borsaistanbul.com.evil.example/veriler/pay-piyasasi-verileri",
            "https://www.borsaistanbul.com/other",
        ):
            with self.subTest(url=url):
                with self.assertRaisesRegex(KAPInputError, "untrusted_or_future_bist_source"):
                    audit(
                        self.kap, self.kap_sha, DAY, self.bist,
                        hashlib.sha256(self.bist.read_bytes()).hexdigest(),
                        DAY, as_of=DAY, bist_url=url,
                    )

    def test_strict_reports_blocked_and_no_overwrite(self):
        digest = self.write_bist("AAAA,ABCDA,YILDIZ PAZAR,,2026-11-21\n")
        target = self.root / "crosswalk.json"
        argv = [
            "script", "--kap-csv", str(self.kap), "--kap-sha256", self.kap_sha,
            "--kap-date", DAY.isoformat(), "--bist-csv", str(self.bist),
            "--bist-sha256", digest, "--bist-date", DAY.isoformat(),
            "--as-of", DAY.isoformat(), "--report-json", str(target), "--strict",
        ]
        with patch("sys.argv", argv), redirect_stdout(io.StringIO()):
            self.assertEqual(main(), 2)
        data = json.loads(target.read_text(encoding="utf-8"))
        self.assertFalse(data["broker_mapping_verified"])
        self.assertEqual(data["orders"], 0)
        with patch("sys.argv", argv), redirect_stdout(io.StringIO()):
            self.assertEqual(main(), 1)

    def test_100_plus_kap_codes_not_truncated(self):
        rows = "".join(
            f"YILDIZ PAZAR,K{i:04d},Ornek {i},2026-11-21,\n"
            for i in range(125)
        )
        self.kap_sha = self.write_kap(rows)
        report = self.call(bist=False)
        self.assertEqual(report["kap_equity_market_candidate_codes"], 125)
        self.assertEqual(len(report["kap_codes_without_declared_instruments_full"]), 125)


if __name__ == "__main__":
    unittest.main()
