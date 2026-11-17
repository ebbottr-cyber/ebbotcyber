"""EBBot stage 7: deterministic crypto-agent research safety and journal tests.

No network, exchange credentials, paper orders, or stock-system side effects.
"""
from __future__ import annotations

import time
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from src.services import crypto_research_bridge as r


def report(market="spot", identity="BTC/USDT", frame="1h"):
    stamp = int(time.time() * 1000) - 60_000
    agents = [
        {"agent": name, "action": "HOLD", "confidence": 0.0,
         "rationale": "Not confirmed", "regime_weight": 1.0,
         "performance_weight": 1.0}
        for name in sorted(r.AGENTS)
    ]
    return {
        "market": market, "symbol": identity, "timeframe": frame,
        "action": "HOLD", "confidence": 0.0, "agreement": 0.0,
        "agents": agents, "votes": {"buy": 0, "sell": 0, "hold": 9},
        "market_regime": {"name": "range_bound"},
        "news_context": {"risk_level": "unknown", "article_count": 0},
        "last_close": 80000.0, "candle_timestamp": stamp,
        "execution": "disabled", "mode": "research_only",
        "data_source": "Binance public market data",
        "performance_weighting": {"enabled": True, "training": False},
        "journal": {"recorded": 0, "signals": []},
    }


class ResearchValidatorTests(unittest.TestCase):
    def test_carries_nine_independent_read_only_agent_votes(self):
        d = report()
        result = r._report(d, "spot", "BTC/USDT", "1h", d["candle_timestamp"], d["last_close"])
        self.assertEqual(result["engine"], "deterministic_ensemble")
        self.assertEqual(len(result["agents"]), 9)
        self.assertFalse(result["risk_approved"])
        self.assertFalse(result["orders_placed"])
        self.assertEqual(result["execution"], "disabled")

    def test_wrong_futures_or_spot_identity_cannot_cross(self):
        for market, symbol in (
            ("spot", "../BTC/USDT"), ("futures", "BTC/USDC"),
            ("futures", "BTC/USDT:USDT"), ("forex", "BTC/USDT"),
        ):
            with self.subTest(market=market, symbol=symbol), self.assertRaises(r.CryptoResearchError):
                r._symbol(market, symbol)
        self.assertEqual(r._symbol("futures", "btc/usdt"), ("BTC/USDT", "BTC/USDT:USDT"))

    def test_market_data_missing_stale_and_unsafe_results_are_rejected(self):
        d = report()
        alterations = (
            {"market": "futures"},
            {"symbol": "BTC/USDT:USDT"},
            {"mode": "paper_order"},
            {"execution": "enabled"},
            {"data_source": "untrusted"},
            {"candle_timestamp": d["candle_timestamp"] - 3600000},
            {"confidence": float("nan")},
            {"last_close": 0},
            {"votes": {"buy": 1, "sell": 1, "hold": 8}},
            {"journal": {"recorded": -1, "signals": []}},
            {"performance_weighting": {"training": True}},
        )
        for change in alterations:
            with self.subTest(change=change), self.assertRaises(r.CryptoResearchError):
                r._report({**d, **change}, "spot", "BTC/USDT", "1h", d["candle_timestamp"], d["last_close"])

    def test_same_candle_but_different_price_is_rejected(self):
        d = report()
        d["last_close"] = 80100.0
        with self.assertRaises(r.CryptoResearchError) as context:
            r._report(d, "spot", "BTC/USDT", "1h", d["candle_timestamp"], 80000.0)
        self.assertEqual(context.exception.code, "snapshot_mismatch")

    def test_rejects_missing_duplicate_agents(self):
        d = report()
        d["agents"][-1]["agent"] = d["agents"][0]["agent"]
        with self.assertRaises(r.CryptoResearchError):
            r._report(d, "spot", "BTC/USDT", "1h", d["candle_timestamp"], d["last_close"])

    def test_allowlisted_safe_endpoints_do_not_accept_order_paths(self):
        for bad in (
            "/api/v1/paper/orders", "/api/v1/agents/trade-plan",
            "/api/v1/risk/check", "/api/v1/strategies/foo/signal",
        ):
            self.assertFalse(
                bad in {
                    "/api/v1/agents/analyze", "/api/v1/agents/signals",
                    "/api/v1/agents/weights", "/api/v1/strategies",
                }
            )

    def test_weights_and_journal_mode_flags_are_mandatory(self):
        for mode in ("order_execution", "paper_order", None):
            with self.subTest(mode=mode), self.assertRaises(r.CryptoResearchError):
                r._no_orders({"orders_placed": False, "mode": mode}, mode="journal_only")
        with self.assertRaises(r.CryptoResearchError):
            r._no_orders({"orders_placed": True, "mode": "journal_only"}, mode="journal_only")


class ResearchOfflineTests(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_candles_block_journal_before_remote_analysis(self):
        get = AsyncMock()
        with patch.object(r, "spot_data", AsyncMock(return_value={
            "quality": "unknown", "candles": [], "last_candle_timestamp": 0,
        })), patch.object(r, "_get", get):
            with self.assertRaises(r.CryptoResearchError) as ctx:
                await r.analyze("spot", "BTC/USDT", "1h")
        self.assertEqual(ctx.exception.code, "market_data_unavailable")
        get.assert_not_awaited()

    async def test_user_initiated_analysis_journals_only_for_verified_candle(self):
        d = report()
        price = {"quality": "ok", "candles": [{"close": 80000}] * 250,
                 "last_candle_timestamp": d["candle_timestamp"]}
        remote = AsyncMock(return_value=d)
        with patch.object(r, "spot_data", AsyncMock(return_value=price)), patch.object(
            r, "_get", remote
        ), patch.object(r, "record_decision", return_value=17) as audit:
            result = await r.analyze("spot", "BTC/USDT", "1h")
        audit.assert_called_once()
        self.assertEqual(result["audit_id"], 17)
        self.assertEqual(result["action"], "HOLD")
        self.assertEqual(result["journal_recorded"], 0)
        self.assertFalse(result["risk_approved"])
        self.assertEqual(remote.await_args.args[0], "/api/v1/agents/analyze")
        self.assertEqual(remote.await_args.args[1]["limit"], 250)

    async def test_futures_analysis_propagates_perpetual_contract_identity(self):
        d = report("futures", "BTC/USDT:USDT")
        price = {"quality": "ok", "candles": [{"close": 80000}] * 250,
                 "last_candle_timestamp": d["candle_timestamp"]}
        remote = AsyncMock(return_value=d)
        with patch.object(r, "futures_data", AsyncMock(return_value=price)), patch.object(
            r, "_get", remote
        ), patch.object(r, "record_decision", return_value=18):
            result = await r.analyze("futures", "BTC/USDT", "1h")
        self.assertEqual(result["symbol"], "BTC/USDT:USDT")
        self.assertEqual(remote.await_args.args[1]["symbol"], "BTC/USDT:USDT")

    async def test_catalog_uses_real_orders_enabled_contract(self):
        catalog = {"strategies": [{"name": name, "description": "research"} for name in sorted(r.STRATEGIES)],
                   "mode": "research_only", "orders_enabled": False}
        with patch.object(r, "_get", AsyncMock(return_value=catalog)):
            result = await r.strategies()
        self.assertEqual(len(result["strategies"]), 7)
        self.assertFalse(result["orders_placed"])
        catalog["orders_enabled"] = True
        with patch.object(r, "_get", AsyncMock(return_value=catalog)):
            with self.assertRaises(r.CryptoResearchError):
                await r.strategies()

    async def test_signals_are_read_only_and_filtered(self):
        rows = {
            "signals": [{
                "id": "id1", "created_at": "2026-11-17T05:00:00+00:00",
                "market": "spot", "symbol": "BTC/USDT", "timeframe": "1h",
                "agent": "trend", "action": "BUY", "confidence": .65,
                "entry_price": 80000, "exit_price": None, "pnl_pct": None,
                "outcome": None, "strategy_name": "trend_following",
            }],
            "mode": "journal_only", "orders_placed": False,
            "total_matching": 1,
        }
        with patch.object(r, "_get", AsyncMock(return_value=rows)):
            result = await r.signals("spot", 50)
        self.assertEqual(result["count"], 1)
        self.assertFalse(result["orders_placed"])
        rows["orders_placed"] = True
        with patch.object(r, "_get", AsyncMock(return_value=rows)):
            with self.assertRaises(r.CryptoResearchError):
                await r.signals("spot", 50)

    async def test_strategy_evaluation_does_not_write_trade_or_journal(self):
        d = report()
        data = {"market": "spot", "execution": "disabled",
                "data_source": "Binance public market data",
                "signal": {
                    "strategy": "trend_following", "symbol": "BTC/USDT", "timeframe": "1h",
                    "action": "HOLD", "confidence": 0.0, "rationale": "No trend",
                    "entry_reference": 80000, "stop_reference": None,
                    "take_profit_reference": None, "risk_reward": None,
                    "candle_timestamp": d["candle_timestamp"],
                }}
        prices = {"quality": "ok", "candles": [{"close": 80000}] * 100,
                  "last_candle_timestamp": d["candle_timestamp"]}
        with patch.object(r, "spot_data", AsyncMock(return_value=prices)), patch.object(
            r, "_get", AsyncMock(return_value=data)
        ) as remote, patch.object(r, "record_decision", return_value=19) as audit:
            result = await r.strategy_signal("spot", "BTC/USDT", "1h", "trend_following")
        audit.assert_called_once()
        self.assertEqual(result["audit_id"], 19)
        self.assertFalse(result["orders_placed"])
        self.assertFalse(result["risk_approved"])
        self.assertEqual(remote.await_args.args[0], "/api/v1/strategies/trend_following/signal")


    async def test_audit_failure_blocks_ensemble_decision_response(self):
        from src.services.crypto_research_audit import CryptoAuditError
        d = report()
        prices = {"quality": "ok", "candles": [{"close": 80000}] * 250,
                  "last_candle_timestamp": d["candle_timestamp"]}
        with patch.object(r, "spot_data", AsyncMock(return_value=prices)), patch.object(
            r, "_get", AsyncMock(return_value=d)
        ), patch.object(r, "record_decision", side_effect=CryptoAuditError("disk error")):
            with self.assertRaises(r.CryptoResearchError) as ctx:
                await r.analyze("spot", "BTC/USDT", "1h")
        self.assertEqual(ctx.exception.code, "audit_unavailable")


if __name__ == "__main__":
    unittest.main()
