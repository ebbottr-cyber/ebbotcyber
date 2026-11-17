"""EBBot stage 9: existing Trading Office paper-ledger read-only contracts.

Synthetic snapshots mirror the inspected Trading Office ledger.py, futures.py,
reporting.py response keys. No Binance, real order or mutation endpoint used.
"""
from __future__ import annotations

import copy
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from src.services import crypto_paper_bridge as paper

NOW = datetime.now(timezone.utc).isoformat()


def spot_account():
    return {
        "mode": "paper_only", "persistence": "sqlite_local_persistent",
        "starting_cash": 10000, "cash": 9900, "realized_pnl": 0,
        "order_count": 1,
        "orders": [{
            "id": "paper-order-1", "symbol": "BTC/USDT", "side": "BUY",
            "quantity": 1, "reference_price": 100, "notional": 100,
            "fee": .1, "realized_pnl": 0, "status": "SIMULATED",
            "created_at": NOW,
        }],
        "positions": [{"symbol": "BTC/USDT", "quantity": 1, "average_price": 100.1}],
    }


def spot_portfolio():
    return {
        "mode": "paper_only", "market": "spot",
        "cash": 9900, "equity": 10001,
        "realized_pnl": 0, "unrealized_pnl": .9,
        "valuation_complete": True,
        "positions": [{
            "symbol": "BTC/USDT", "quantity": 1, "average_price": 100.1,
            "mark_price": 101, "market_value": 101,
            "unrealized_pnl": .9,
        }],
    }


def futures_account():
    return {
        "mode": "paper_only", "market": "futures",
        "wallet_balance": 9550, "used_initial_margin": 450,
        "realized_pnl": -.45, "unrealized_pnl": 20,
        "equity": 10020, "valuation_complete": True,
        "daily_risk": {"daily_realized_pnl": -.45, "new_positions_allowed": True},
        "positions": [{
            "symbol": "BTC/USDT:USDT", "side": "LONG",
            "quantity": .1, "entry_price": 9000, "leverage": 2,
            "margin": 450, "mark_price": 9200, "notional": 920,
            "unrealized_pnl": 20, "funding_paid": .2,
            "entry_fee": .45, "opened_at": NOW,
            "estimated_liquidation_price": 4522.5,
        }],
        "trades": [{
            "id": "futures-1", "symbol": "BTC/USDT:USDT",
            "action": "OPEN", "side": "LONG",
            "quantity": .1, "price": 9000,
            "leverage": 2, "fee": .45,
            "realized_pnl": 0, "created_at": NOW,
        }, {
            "id": "funding-1", "symbol": "BTC/USDT:USDT",
            "action": "FUNDING", "side": "LONG",
            "quantity": .1, "price": 9200,
            "leverage": 2, "fee": 0,
            "realized_pnl": -.2, "created_at": NOW,
        }],
    }


def performance():
    return {
        "daily": {"realized_net_pnl": -2, "event_count": 2, "since_utc": NOW},
        "weekly": {"realized_net_pnl": -2, "event_count": 2, "since_utc": NOW},
        "monthly": {"realized_net_pnl": -2, "event_count": 2, "since_utc": NOW},
        "sources": {"spot_ledger": 1, "futures_ledger": 2, "closed_lifecycle_trades": 0},
        "basis": "Trading Office report",
    }


def history():
    return {
        "mode": "paper_only", "count": 2,
        "events": [{
            "id": "funding-1", "symbol": "BTC/USDT:USDT", "market": "futures",
            "source": "futures_ledger", "action": "FUNDING", "side": "LONG",
            "price": 9200, "fee": 0, "event_pnl": -.2, "created_at": NOW,
        }, {
            "id": "paper-order-1", "symbol": "BTC/USDT", "market": "spot",
            "source": "spot_ledger", "side": "BUY",
            "price": 100, "fee": .1, "event_pnl": 0, "created_at": NOW,
        }],
    }


class PaperContractTests(unittest.TestCase):
    def test_existing_spot_ledger_reconciles_market_value(self):
        account = paper.validate_spot_ledger(spot_account())
        view = paper.validate_spot_portfolio(spot_portfolio(), account)
        self.assertEqual(view["market"], "spot")
        self.assertEqual(view["equity"], 10001)
        self.assertEqual(view["positions"][0]["unrealized_pnl"], .9)
        self.assertEqual(account["order_count"], 1)
        self.assertEqual(account["orders"][0]["status"], "SIMULATED")

    def test_existing_futures_margin_and_funding_events(self):
        account = paper.validate_futures_account(futures_account())
        self.assertEqual(account["equity"], 10020)
        self.assertEqual(account["positions"][0]["margin"], 450)
        self.assertEqual(account["positions"][0]["funding_paid"], .2)
        self.assertEqual(account["trades"][1]["action"], "FUNDING")
        self.assertEqual(account["trades"][1]["realized_pnl"], -.2)

    def test_missing_market_quote_never_becomes_zero_equity(self):
        a = spot_account()
        d = spot_portfolio()
        d["valuation_complete"] = False
        d["equity"] = None
        d["unrealized_pnl"] = None
        d["positions"][0].update({
            "mark_price": None, "market_value": None,
            "unrealized_pnl": None,
        })
        result = paper.validate_spot_portfolio(d, paper.validate_spot_ledger(a))
        self.assertIsNone(result["equity"])
        d["equity"] = 9900
        with self.assertRaises(paper.PaperReadError):
            paper.validate_spot_portfolio(d, paper.validate_spot_ledger(a))

    def test_wrong_paper_market_and_live_status_fail(self):
        a = spot_account()
        a["orders"][0]["status"] = "LIVE"
        with self.assertRaises(paper.PaperReadError):
            paper.validate_spot_ledger(a)
        a = spot_account()
        a["orders"][0]["symbol"] = "BTC/USDT:USDT"
        with self.assertRaises(paper.PaperReadError):
            paper.validate_spot_ledger(a)
        f = futures_account()
        f["positions"][0]["symbol"] = "BTC/TRY"
        with self.assertRaises(paper.PaperReadError):
            paper.validate_futures_account(f)

    def test_incomplete_ledger_and_duplicate_ids_fail(self):
        a = spot_account()
        a["order_count"] = 0
        with self.assertRaises(paper.PaperReadError):
            paper.validate_spot_ledger(a)
        a = spot_account()
        a["orders"].append(copy.deepcopy(a["orders"][0]))
        a["order_count"] = 2
        with self.assertRaises(paper.PaperReadError):
            paper.validate_spot_ledger(a)

    def test_unreconciled_source_snapshots_fail(self):
        s = paper.validate_spot_ledger(spot_account())
        view = spot_portfolio()
        view["cash"] += 25
        with self.assertRaises(paper.PaperReadError):
            paper.validate_spot_portfolio(view, s)
        f = futures_account()
        f["wallet_balance"] = 10000
        with self.assertRaises(paper.PaperReadError):
            paper.validate_futures_account(f)

    def test_history_covers_spot_futures_and_funding_without_fabrication(self):
        result = paper.validate_history(history(), 100)
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["events"][0]["action"], "FUNDING")
        self.assertEqual(result["events"][1]["market"], "spot")
        altered = history()
        altered["events"][0]["market"] = "spot"
        with self.assertRaises(paper.PaperReadError):
            paper.validate_history(altered, 100)

    def test_history_and_performance_must_be_complete(self):
        d = history()
        d["count"] = 100
        with self.assertRaises(paper.PaperReadError):
            paper.validate_history(d, 100)
        d = performance()
        d["daily"]["realized_net_pnl"] = float("nan")
        with self.assertRaises(paper.PaperReadError):
            paper.validate_performance(d)


class PaperGatewayTests(unittest.IsolatedAsyncioTestCase):
    async def test_read_only_summary_never_creates_second_paper_account(self):
        responses = {
            "spot-account": spot_account(),
            "spot-portfolio": spot_portfolio(),
            "futures-account": futures_account(),
            "performance": performance(),
        }
        remote = AsyncMock(side_effect=lambda kind, **kwargs: responses[kind])
        with patch.object(paper, "_get", remote):
            value = await paper.read_paper_summary()
        self.assertEqual(value["combined_equity"], 20021)
        self.assertTrue(value["valuation_complete"])
        self.assertFalse(value["safety"]["paper_execution_permitted"])
        self.assertFalse(value["safety"]["real_exchange_orders"])
        self.assertEqual(remote.await_count, 4)
        self.assertEqual([call.args[0] for call in remote.await_args_list],
                         ["spot-account", "spot-portfolio", "futures-account", "performance"])

    async def test_history_filters_without_upstream_order_mutations(self):
        with patch.object(paper, "_get", AsyncMock(return_value=history())) as call:
            value = await paper.read_paper_history("futures", 100)
        self.assertEqual(value["count"], 1)
        self.assertEqual(value["events"][0]["action"], "FUNDING")
        self.assertEqual(call.await_args.args[0], "history")
        self.assertEqual(call.await_args.kwargs["limit"], 100)

    async def test_order_paths_are_not_allowlisted(self):
        for forbidden in ("orders", "futures-open", "futures-close", "reset", "../paper/orders"):
            with self.subTest(forbidden=forbidden), self.assertRaises(paper.PaperReadError):
                await paper._get(forbidden)


if __name__ == "__main__":
    unittest.main()
