"""Offline EBBot crypto risk-engine regression tests.

Trusted facts are synthetic test fixtures, NOT displayed as real market data.
The engine must never authorize Paper or real exchange orders.
"""
from __future__ import annotations

import copy
import math
import time
import unittest
from datetime import datetime, timezone

from src.services.crypto_risk_engine import RiskInputError, evaluate_risk


def proposal(market="spot"):
    return {
        "market": market, "symbol": "BTC/USDT", "side": "BUY",
        "entry_price": 100.0, "stop_price": 95.0,
        "take_profit_price": 115.0, "risk_percent": 0.5,
        "leverage": 1 if market == "spot" else 3,
    }


def dashboard():
    return {
        "mode": "paper_only", "schema_version": "1.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "safety": {"real_exchange_orders": False, "live_trading_enabled": False},
        "portfolio": {
            "currency": "USDT",
            "combined": {"equity": 20000.0, "valuation_complete": True},
            "spot": {
                "market": "spot", "mode": "paper_only",
                "equity": 10000.0, "cash": 10000.0,
                "positions": [], "valuation_complete": True,
            },
            "futures": {
                "market": "futures", "mode": "paper_only",
                "equity": 10000.0, "wallet_balance": 10000.0, "positions": [],
                "valuation_complete": True,
                "daily_risk": {
                    "daily_realized_pnl": 0.0, "projected_daily_pnl": 0.0,
                    "daily_loss_limit": 200.0, "valuation_complete": True,
                    "new_positions_allowed": True,
                },
            },
        },
        "risk": {"daily_guard": {
            "mode": "paper_only", "real_exchange_orders": False,
            "new_positions_allowed": True,
            "level": "normal", "risk_multiplier": 1.0,
        }},
    }


def quote(market="spot"):
    return {
        "market": market, "symbol": "BTC/USDT", "quality": "ok",
        "last": 100.0, "bid": 99.99, "ask": 100.01,
    }


def depth(market="spot"):
    return {
        "market": market, "symbol": "BTC/USDT", "quality": "ok",
        "bid_quote_depth": 100000.0, "ask_quote_depth": 100000.0,
    }


def funding():
    return {"market": "futures", "symbol": "BTC/USDT", "funding_rate": 0.0001}


def check(market="spot", *, p=None, d=None, q=None, b=None, f=None, daily=0):
    return evaluate_risk(
        p if p is not None else proposal(market),
        d if d is not None else dashboard(),
        daily,
        q if q is not None else quote(market),
        b if b is not None else depth(market),
        f if f is not None else (funding() if market == "futures" else None),
    )


class IndependentCryptoRiskTests(unittest.TestCase):
    def test_spot_review_is_never_execution_approval(self):
        result = check()
        self.assertEqual(result["status"], "REVIEW_ONLY")
        self.assertTrue(result["risk_review_passed"])
        self.assertFalse(result["paper_execution_permitted"])
        self.assertFalse(result["real_exchange_orders"])
        self.assertFalse(result["risk_approved"])
        self.assertEqual(result["execution"], "disabled")
        self.assertLessEqual(result["estimated_loss_with_costs"], result["risk_budget"] + .000001)

    def test_futures_review_is_never_execution_approval(self):
        result = check("futures")
        self.assertEqual(result["status"], "REVIEW_ONLY")
        self.assertEqual(result["market"], "futures")
        self.assertGreater(result["estimated_one_period_funding_reserve"], 0)
        self.assertFalse(result["paper_execution_permitted"])
        self.assertLessEqual(result["estimated_margin"], result["estimated_position_notional"])

    def test_unavailable_valuation_never_becomes_zero_balance(self):
        d = dashboard()
        d["portfolio"]["combined"]["valuation_complete"] = False
        d["portfolio"]["combined"]["equity"] = None
        with self.assertRaises(RiskInputError):
            check(d=d)
        d = dashboard()
        d["portfolio"]["spot"]["equity"] = None
        with self.assertRaises(RiskInputError):
            check(d=d)

    def test_daily_realized_spot_loss_blocks(self):
        result = check(daily=-201)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("spot_daily_loss_limit", result["reasons"])
        self.assertFalse(result["risk_review_passed"])

    def test_daily_futures_loss_and_upstream_guard_block(self):
        d = dashboard()
        d["portfolio"]["futures"]["daily_risk"]["daily_realized_pnl"] = -205
        self.assertIn("futures_daily_loss_limit", check("futures", d=d)["reasons"])
        d = dashboard()
        d["risk"]["daily_guard"]["new_positions_allowed"] = False
        result = check("futures", d=d)
        self.assertIn("upstream_risk_guard_blocked", result["reasons"])

    def test_upstream_progressive_throttle_cannot_be_bypassed(self):
        baseline = check()
        d = dashboard()
        d["risk"]["daily_guard"]["level"] = "elevated"
        d["risk"]["daily_guard"]["risk_multiplier"] = .75
        lowered = check(d=d)
        self.assertLess(lowered["risk_budget"], baseline["risk_budget"])
        self.assertAlmostEqual(lowered["upstream_risk_multiplier"], .75)
        d["risk"]["daily_guard"]["risk_multiplier"] = 0.0
        with self.assertRaises(RiskInputError):
            check(d=d)

    def test_future_wallet_balance_and_combined_daily_risk_block(self):
        d = dashboard()
        d["portfolio"]["futures"]["wallet_balance"] = 0
        self.assertIn(
            "insufficient_futures_wallet_balance",
            check("futures", d=d)["reasons"],
        )
        d = dashboard()
        d["portfolio"]["spot"]["equity"] = 10000
        d["portfolio"]["futures"]["equity"] = 10000
        d["portfolio"]["futures"]["daily_risk"]["daily_realized_pnl"] = -180
        d["portfolio"]["futures"]["daily_risk"]["projected_daily_pnl"] = -180
        # Both account losses together breach the combined 2% daily limit.
        result = check("futures", d=d, daily=-230)
        self.assertIn("combined_daily_loss_limit", result["reasons"])

    def test_existing_unknown_or_large_position_exposure_blocks(self):
        d = dashboard()
        d["portfolio"]["futures"]["positions"] = [{
            "symbol": "BTC/USDT:USDT", "side": "LONG", "quantity": 3,
            "mark_price": 100, "margin": 250,
        }]
        result = check("futures", d=d)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("aggregate_risk_limit", result["reasons"])
        d["portfolio"]["futures"]["positions"][0]["mark_price"] = None
        with self.assertRaises(RiskInputError):
            check("futures", d=d)

    def test_wrong_market_missing_quote_depth_and_funding_fail_closed(self):
        for change in (
            {"market": "futures"}, {"last": 0},
            {"quality": "unknown"}, {"bid": None},
        ):
            with self.subTest(change=change), self.assertRaises(RiskInputError):
                check(q={**quote(), **change})
        with self.assertRaises(RiskInputError):
            check(b={**depth(), "quality": "unknown"})
        with self.assertRaises(RiskInputError):
            check("futures", f={"market": "futures", "symbol": "BTC/USDT", "funding_rate": None})

    def test_stop_target_direction_and_leverage_are_mandatory(self):
        for change in (
            {"stop_price": 101}, {"take_profit_price": 99},
            {"leverage": 2}, {"risk_percent": 2.5},
            {"side": "SELL"}, {"entry_price": math.nan},
            {"stop_price": 100 - 1e-11},
        ):
            with self.subTest(change=change), self.assertRaises(RiskInputError):
                check(p={**proposal(), **change})
        p = proposal("futures")
        p.update({"side": "SELL", "stop_price": 105, "take_profit_price": 85})
        self.assertEqual(check("futures", p=p)["status"], "REVIEW_ONLY")

    def test_price_mismatch_bad_risk_reward_and_liquidity_block(self):
        with self.assertRaises(RiskInputError) as ctx:
            check(p={**proposal(), "entry_price": 102})
        self.assertEqual(ctx.exception.code, "entry_price_mismatch")
        result = check(p={**proposal(), "take_profit_price": 101})
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("risk_reward_below_1_5_after_costs", result["reasons"])
        result = check(b={**depth(), "ask_quote_depth": 0.001})
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("insufficient_risk_or_liquidity_budget", result["reasons"])

    def test_invalid_currency_or_mismatched_account_balances_fail(self):
        d = dashboard()
        d["portfolio"]["currency"] = "USD"
        with self.assertRaises(RiskInputError):
            check(d=d)
        d = dashboard()
        d["portfolio"]["combined"]["equity"] = 9000
        with self.assertRaises(RiskInputError):
            check(d=d)

    def test_old_portfolio_timestamp_and_unsafe_trading_mode_fail(self):
        d = dashboard()
        d["generated_at"] = "2020-01-01T00:00:00+00:00"
        with self.assertRaises(RiskInputError):
            check(d=d)
        d = dashboard()
        d["safety"]["real_exchange_orders"] = True
        with self.assertRaises(RiskInputError):
            check(d=d)


if __name__ == "__main__":
    unittest.main()
