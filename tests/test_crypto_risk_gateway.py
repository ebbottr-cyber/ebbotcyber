"""EBBot Spot ledger and durable risk audit tests; never contact Binance."""
from __future__ import annotations

import copy
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from src.services.crypto_risk_engine import RiskInputError
from src.services.crypto_risk_gateway import spot_daily_from_ledger
from src.services.crypto_risk_audit import RiskAuditError, record_risk_review, recent_risk_reviews
from src.services import crypto_research_audit as store


def paper():
    now = datetime.now(timezone.utc).isoformat()
    account = {
        "mode": "paper_only", "cash": 9900.0, "order_count": 2,
        "orders": [
            {"side": "BUY", "status": "SIMULATED", "fee": 1.0,
             "realized_pnl": 0.0, "created_at": now},
            {"side": "SELL", "status": "SIMULATED", "fee": 1.2,
             "realized_pnl": -10.0, "created_at": now},
        ],
    }
    spot = {"mode": "paper_only", "cash": 9900.0}
    return account, spot


def review():
    return {
        "status": "BLOCKED", "risk_review_passed": False,
        "market": "spot", "symbol": "BTC/USDT", "side": "BUY",
        "paper_execution_permitted": False,
        "risk_approved": False, "real_exchange_orders": False,
        "execution": "disabled", "reasons": ["spot_daily_loss_limit"],
    }


class LedgerRiskTests(unittest.TestCase):
    def test_reads_all_validated_orders_not_invented_zero_loss(self):
        account, spot = paper()
        self.assertAlmostEqual(spot_daily_from_ledger(account, spot), -11.0)

    def test_rejects_missing_order_count(self):
        account, spot = paper()
        del account["order_count"]
        with self.assertRaises(RiskInputError):
            spot_daily_from_ledger(account, spot)

    def test_rejects_missing_or_corrupt_order_history(self):
        account, spot = paper()
        account["orders"] = None
        with self.assertRaises(RiskInputError):
            spot_daily_from_ledger(account, spot)
        account, spot = paper()
        account["orders"][0]["fee"] = float("nan")
        with self.assertRaises(RiskInputError):
            spot_daily_from_ledger(account, spot)
        account, spot = paper()
        account["orders"][0]["status"] = "LIVE"
        with self.assertRaises(RiskInputError):
            spot_daily_from_ledger(account, spot)

    def test_rejects_unreconciled_cash_between_reads(self):
        account, spot = paper()
        spot["cash"] = 9000
        with self.assertRaises(RiskInputError):
            spot_daily_from_ledger(account, spot)

    def test_no_orders_is_zero_only_after_verified_empty_ledger(self):
        account, spot = paper()
        account["orders"] = []
        account["order_count"] = 0
        self.assertEqual(spot_daily_from_ledger(account, spot), 0)


class RiskAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        original = store.DB_PATH
        store.DB_PATH = Path(self.temp.name) / "crypto" / "risk.sqlite3"
        self.addCleanup(setattr, store, "DB_PATH", original)

    def test_review_history_stays_crypto_only_and_order_disabled(self):
        record = review()
        idx = record_risk_review({
            "market": "spot", "symbol": "BTC/USDT", "side": "BUY",
        }, record)
        self.assertGreater(idx, 0)
        hist = recent_risk_reviews()
        self.assertEqual(hist["count"], 1)
        self.assertEqual(hist["reviews"][0]["status"], "BLOCKED")
        self.assertFalse(hist["reviews"][0]["paper_execution_permitted"])
        with sqlite3.connect(store.DB_PATH) as db:
            tables = [row[0] for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )]
        self.assertIn("crypto_risk_reviews", tables)
        self.assertNotIn("paper_orders", tables)

    def test_review_audit_refuses_execution_authorization(self):
        for change in (
            {"risk_approved": True}, {"paper_execution_permitted": True},
            {"real_exchange_orders": True}, {"execution": "enabled"},
        ):
            with self.subTest(change=change), self.assertRaises(RiskAuditError):
                record_risk_review({"market": "spot", "symbol": "BTC/USDT"}, {**review(), **change})
        self.assertEqual(recent_risk_reviews()["count"], 0)

    def test_db_failure_denies_review_persistence(self):
        with patch.object(store, "_connect", side_effect=sqlite3.OperationalError("denied")):
            with self.assertRaises(RiskAuditError):
                record_risk_review({"market": "spot", "symbol": "BTC/USDT"}, review())


if __name__ == "__main__":
    unittest.main()
