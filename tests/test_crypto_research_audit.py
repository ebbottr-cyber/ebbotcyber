"""Audit persistence safety: all crypto decisions incl HOLD, never orders."""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.services import crypto_research_audit as a


def report(action="HOLD"):
    return {
        "market": "spot", "symbol": "BTC/USDT", "timeframe": "1h",
        "action": action, "confidence": 0.0 if action == "HOLD" else 0.7,
        "candle_timestamp": 1795000000000, "execution": "disabled",
        "risk_approved": False, "orders_placed": False,
        "journal_recorded": 0, "agents": [{"agent": "trend", "action": action}],
    }


class CryptoAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.original_path = a.DB_PATH
        a.DB_PATH = Path(self.temp.name) / "private" / "research_audit.sqlite3"
        self.addCleanup(setattr, a, "DB_PATH", self.original_path)

    def test_every_manual_hold_buy_sell_is_persisted(self):
        one = a.record_decision("ensemble", report("HOLD"))
        two = a.record_decision("ensemble", report("BUY"))
        three = a.record_decision("strategy", report("SELL"))
        self.assertEqual([one, two, three], [1, 2, 3])
        items = a.recent_decisions(10)
        self.assertEqual([row["action"] for row in items["decisions"]], ["SELL", "BUY", "HOLD"])
        self.assertTrue(all(not row["orders_placed"] and not row["risk_approved"] for row in items["decisions"]))

    def test_audit_does_not_mutate_stock_database(self):
        a.record_decision("ensemble", report())
        with sqlite3.connect(a.DB_PATH) as db:
            names = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertIn("crypto_research_decisions", names)
        self.assertNotIn("stock_info", names)
        self.assertNotIn("paper_orders", names)

    def test_live_execution_flags_are_rejected_before_write(self):
        for change in (
            {"risk_approved": True}, {"orders_placed": True},
            {"execution": "enabled"}, {"action": "EXECUTE"},
            {"market": "stocks"},
        ):
            with self.subTest(change=change), self.assertRaises(a.CryptoAuditError):
                a.record_decision("ensemble", {**report(), **change})
        self.assertEqual(a.recent_decisions()["count"], 0)

    def test_secret_strings_cannot_be_persisted(self):
        data = report()
        data["rationale"] = "Bearer abcdefghijklmnopqrstuvwxyz0123456789"
        with self.assertRaises(a.CryptoAuditError):
            a.record_decision("ensemble", data)
        self.assertEqual(a.recent_decisions()["count"], 0)

    def test_io_error_fails_closed(self):
        with patch.object(a, "_connect", side_effect=sqlite3.OperationalError("readonly")):
            with self.assertRaises(a.CryptoAuditError):
                a.record_decision("ensemble", report())

    def test_recent_history_has_no_raw_rationales(self):
        data = report()
        data["agents"][0]["rationale"] = "private explanation"
        a.record_decision("ensemble", data)
        entry = a.recent_decisions()["decisions"][0]
        self.assertNotIn("agents", entry)
        self.assertNotIn("rationale", entry)
        self.assertEqual(entry["journal_recorded"], 0)


if __name__ == "__main__":
    unittest.main()
