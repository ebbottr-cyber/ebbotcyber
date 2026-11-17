"""Independent, fail-closed EBBot crypto risk preflight (NO execution grant).

Grounded in Trading Office risk.models, risk.engine, paper.portfolio_guard
and paper.futures. This is a decision-support calculation only: it CANNOT
authorize a Spot/Futures paper order or a real exchange order.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

SOURCE_LIMITS = {
    "max_risk_per_trade_pct": 2.0,
    "default_risk_per_trade_pct": 0.5,
    "max_aggregate_risk_pct": 2.0,
    "max_gross_futures_pct": 100.0,
    "max_directional_futures_pct": 70.0,
    "max_single_futures_pct": 50.0,
    "max_spot_position_pct": 20.0,
    "max_leverage": 5,
    "daily_loss_ceiling_usdt": 200.0,
    "max_stop_distance_pct": 10.0,
    "maintenance_margin_proxy": 0.005,
    # Conservative research assumptions; NOT actual Binance fee tiers.
    "fee_rate_per_side": 0.001,
    "slippage_rate_per_side": 0.0005,
    "funding_periods_reserved": 1,
}


class RiskInputError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _number(x: Any, label: str, *, positive: bool = False, nonnegative: bool = False) -> float:
    if isinstance(x, bool) or not isinstance(x, (float, int)):
        raise RiskInputError(label)
    try:
        v = float(x)
    except (OverflowError, ValueError):
        raise RiskInputError(label) from None
    if not math.isfinite(v) or (positive and v <= 0) or (nonnegative and v < 0):
        raise RiskInputError(label)
    return v


def _map(x: Any, label: str) -> dict:
    if not isinstance(x, dict):
        raise RiskInputError(label)
    return x


def _list(x: Any, label: str) -> list:
    if not isinstance(x, list):
        raise RiskInputError(label)
    return x


def _age_seconds(raw: Any) -> float:
    if not isinstance(raw, str):
        raise RiskInputError("stale_portfolio")
    try:
        t = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if t.tzinfo is None or t.utcoffset() is None:
            raise ValueError()
        return (datetime.now(timezone.utc) - t.astimezone(timezone.utc)).total_seconds()
    except (ValueError, OverflowError):
        raise RiskInputError("stale_portfolio") from None


def _positions(market: str, records: Any) -> tuple[float, float, float, float, dict[str, float]]:
    """Conservative proxy: existing Spot positions risk 100% of market value;
    Futures positions risk all remaining isolated margin because no stop is
    stored in Trading Office's futures_positions table.
    """
    gross = long = short = risk = 0.0
    by_symbol: dict[str, float] = {}
    for p in _list(records, "positions_unavailable"):
        p = _map(p, "invalid_position")
        symbol = p.get("symbol")
        if not isinstance(symbol, str) or not symbol:
            raise RiskInputError("invalid_position")
        qty = _number(p.get("quantity"), "invalid_position", positive=True)
        mark = _number(p.get("mark_price"), "invalid_position", positive=True)
        notional = qty * mark
        if market == "spot":
            exposure_risk = notional
            direction = "BUY"
        else:
            direction = p.get("side")
            if direction not in ("LONG", "SHORT"):
                raise RiskInputError("invalid_position")
            exposure_risk = _number(p.get("margin"), "invalid_position", nonnegative=True)
        gross += notional
        risk += exposure_risk
        if direction in ("LONG", "BUY"):
            long += notional
        else:
            short += notional
        by_symbol[symbol] = by_symbol.get(symbol, 0.0) + notional
    if not all(math.isfinite(x) for x in (gross, long, short, risk, *by_symbol.values())):
        raise RiskInputError("invalid_position")
    return gross, long, short, risk, by_symbol


def evaluate_risk(proposal: dict, dashboard: dict, spot_daily_pnl: float,
                  quote: dict, depth: dict, funding: dict | None = None) -> dict:
    """Validate trusted paper-account facts + independent public market data.

    Returns a binding BLOCK for invalid conditions, or REVIEW_ONLY with an
    estimated size. Never produces an execution permit or transferable token.
    """
    p = _map(proposal, "invalid_request")
    market = p.get("market")
    side = p.get("side")
    symbol = p.get("symbol")
    if market not in ("spot", "futures") or side not in ("BUY", "SELL"):
        raise RiskInputError("invalid_request")
    if market == "spot" and side != "BUY":
        raise RiskInputError("spot_short_forbidden")
    if not isinstance(symbol, str) or not symbol.endswith("/USDT"):
        raise RiskInputError("invalid_symbol")

    entry = _number(p.get("entry_price"), "invalid_entry", positive=True)
    stop = _number(p.get("stop_price"), "invalid_stop", positive=True)
    target = _number(p.get("take_profit_price"), "invalid_target", positive=True)
    risk_pct = _number(p.get("risk_percent", 0.5), "invalid_risk_pct", positive=True)
    lev = p.get("leverage", 1)
    if isinstance(lev, bool) or not isinstance(lev, int):
        raise RiskInputError("invalid_leverage")
    if not 1 <= lev <= SOURCE_LIMITS["max_leverage"] or (market == "spot" and lev != 1):
        raise RiskInputError("invalid_leverage")
    if risk_pct > SOURCE_LIMITS["max_risk_per_trade_pct"]:
        raise RiskInputError("invalid_risk_pct")
    if side == "BUY" and not (stop < entry < target) or side == "SELL" and not (target < entry < stop):
        raise RiskInputError("invalid_stop_target_direction")
    distance = abs(entry - stop) / entry
    reward = abs(target - entry) / entry
    if not 1e-9 < distance <= .10 or reward <= 0:
        raise RiskInputError("invalid_stop_distance")

    d = _map(dashboard, "unavailable_portfolio")
    if d.get("mode") != "paper_only" or d.get("schema_version") != "1.1":
        raise RiskInputError("unsafe_portfolio_mode")
    if not -300 <= _age_seconds(d.get("generated_at")) <= 90:
        raise RiskInputError("stale_portfolio")
    safety = _map(d.get("safety"), "unsafe_portfolio_mode")
    if safety.get("real_exchange_orders") is not False or safety.get("live_trading_enabled") is not False:
        raise RiskInputError("unsafe_portfolio_mode")
    portfolio = _map(d.get("portfolio"), "unavailable_portfolio")
    combined = _map(portfolio.get("combined"), "unavailable_portfolio")
    if combined.get("valuation_complete") is not True:
        raise RiskInputError("incomplete_valuation")
    _number(combined.get("equity"), "incomplete_valuation", positive=True)
    paper = _map(portfolio.get(market), "unavailable_portfolio")
    if paper.get("market") != market or paper.get("mode") != "paper_only":
        raise RiskInputError("unavailable_portfolio")
    if paper.get("valuation_complete") is not True:
        raise RiskInputError("incomplete_valuation")
    equity = _number(paper.get("equity"), "incomplete_valuation", positive=True)
    if portfolio.get("currency") not in (None, "USDT"):
        raise RiskInputError("unsupported_currency")

    spot = _map(portfolio.get("spot"), "unavailable_portfolio")
    future = _map(portfolio.get("futures"), "unavailable_portfolio")
    if spot.get("valuation_complete") is not True or future.get("valuation_complete") is not True:
        raise RiskInputError("incomplete_valuation")
    sgross, _, _, srisk, sby = _positions("spot", spot.get("positions"))
    fgross, flong, fshort, frisk, fby = _positions("futures", future.get("positions"))
    spot_equity = _number(spot.get("equity"), "incomplete_valuation", positive=True)
    futures_equity = _number(future.get("equity"), "incomplete_valuation", positive=True)
    if abs(spot_equity + futures_equity - _number(combined.get("equity"), "incomplete_valuation", positive=True)) > max(1e-5, combined["equity"] * 1e-6):
        raise RiskInputError("portfolio_reconciliation_failed")
    if sgross > spot_equity * 1.01 or fgross > futures_equity * 5.01:
        raise RiskInputError("portfolio_reconciliation_failed")

    _number(spot_daily_pnl, "spot_daily_pnl_unavailable")
    daily = _map(future.get("daily_risk"), "futures_daily_risk_unavailable")
    if daily.get("valuation_complete") is not True:
        raise RiskInputError("futures_daily_risk_unavailable")
    futures_daily_pnl = _number(daily.get("daily_realized_pnl"), "futures_daily_risk_unavailable")
    projected = _number(daily.get("projected_daily_pnl"), "futures_daily_risk_unavailable")
    daily_limit = min(
        _number(daily.get("daily_loss_limit"), "futures_daily_risk_unavailable", positive=True),
        SOURCE_LIMITS["daily_loss_ceiling_usdt"], futures_equity * .02,
    )
    risk_root = _map(d.get("risk"), "risk_guard_unavailable")
    guard = _map(risk_root.get("daily_guard"), "risk_guard_unavailable")
    if guard.get("mode") != "paper_only" or guard.get("real_exchange_orders") is not False:
        raise RiskInputError("risk_guard_unavailable")
    if not isinstance(guard.get("new_positions_allowed"), bool) or not isinstance(daily.get("new_positions_allowed"), bool):
        raise RiskInputError("risk_guard_unavailable")
    if guard.get("level") not in ("normal", "elevated", "critical", "blocked"):
        raise RiskInputError("risk_guard_unavailable")
    throttle = _number(guard.get("risk_multiplier"), "risk_guard_unavailable", nonnegative=True)
    if throttle > 1 or (guard["new_positions_allowed"] is True and throttle == 0):
        raise RiskInputError("risk_guard_unavailable")

    if not isinstance(quote, dict) or quote.get("quality") != "ok" or quote.get("market") != market or quote.get("symbol") != symbol:
        raise RiskInputError("price_unavailable")
    latest = _number(quote.get("last"), "price_unavailable", positive=True)
    if abs(entry / latest - 1) > .005:
        raise RiskInputError("entry_price_mismatch")
    bid = _number(quote.get("bid"), "bid_ask_unavailable", positive=True)
    ask = _number(quote.get("ask"), "bid_ask_unavailable", positive=True)
    if bid > ask or (ask - bid) / latest > .01:
        raise RiskInputError("spread_excessive")
    if not isinstance(depth, dict) or depth.get("market") != market or depth.get("symbol") != symbol or depth.get("quality") != "ok":
        raise RiskInputError("depth_unavailable")
    bid_depth = _number(depth.get("bid_quote_depth"), "depth_unavailable", positive=True)
    ask_depth = _number(depth.get("ask_quote_depth"), "depth_unavailable", positive=True)
    side_depth = ask_depth if side == "BUY" else bid_depth

    funding_rate = 0.0
    if market == "futures":
        if not isinstance(funding, dict) or funding.get("market") != "futures" or funding.get("symbol") != symbol:
            raise RiskInputError("funding_unavailable")
        funding_rate = abs(_number(funding.get("funding_rate"), "funding_unavailable"))
        if funding_rate > .1:
            raise RiskInputError("funding_unavailable")

    fee_pct = 2 * SOURCE_LIMITS["fee_rate_per_side"]
    slippage_pct = 2 * SOURCE_LIMITS["slippage_rate_per_side"]
    friction_pct = fee_pct + slippage_pct + funding_rate
    # Trading Office's existing conservative portfolio throttle is binding.
    # Never allow a caller or an AI signal to increase this multiplier.
    budget = equity * risk_pct / 100 * throttle
    unit_risk_pct = distance + friction_pct
    max_notional = budget / unit_risk_pct
    max_market_notional = equity * (.2 if market == "spot" else .5)
    max_notional = min(max_notional, max_market_notional)
    max_notional = min(max_notional, max(0.0, equity * (1 if market == "futures" else .2) - (fgross if market == "futures" else sgross)))
    max_notional = min(max_notional, max(0.0, equity * .5 - fby.get(symbol + ":USDT", fby.get(symbol, 0.0))) if market == "futures" else max(0.0, equity * .2 - sby.get(symbol, 0.0)))
    # Conservative orderbook rule: estimate cannot exceed 10% of displayed side depth.
    max_notional = min(max_notional, side_depth * .1)
    # Flat Spot buying requires actual available cash; no borrowing.
    if market == "spot":
        cash = _number(spot.get("cash"), "spot_cash_unavailable", nonnegative=True)
        max_notional = min(max_notional, cash / (1 + SOURCE_LIMITS["fee_rate_per_side"]))

    quantity = math.floor(max(0.0, max_notional / entry) * 1e8) / 1e8
    notional = quantity * entry
    estimated_loss = notional * unit_risk_pct
    reward_net = notional * (reward - friction_pct)
    risk_reward_net = reward_net / estimated_loss if estimated_loss > 0 else None
    margin_needed = notional / lev
    liquidation_buffer = (1 / lev - SOURCE_LIMITS["maintenance_margin_proxy"]) if market == "futures" else None
    existing_market_risk = srisk if market == "spot" else frisk
    total_risk_pct = (existing_market_risk + estimated_loss) / equity * 100

    reasons = []
    if (guard["new_positions_allowed"] is not True or daily["new_positions_allowed"] is not True
            or guard["level"] == "blocked"):
        reasons.append("upstream_risk_guard_blocked")
    if market == "spot" and spot_daily_pnl <= -min(200.0, spot_equity * .02):
        reasons.append("spot_daily_loss_limit")
    if market == "futures" and min(futures_daily_pnl, projected) <= -daily_limit:
        reasons.append("futures_daily_loss_limit")
    if market == "futures" and (fgross + notional) / futures_equity > 1.0:
        reasons.append("gross_futures_limit")
    if market == "futures" and (
        (flong + (notional if side == "BUY" else 0)) / futures_equity > .70 or
        (fshort + (notional if side == "SELL" else 0)) / futures_equity > .70
    ):
        reasons.append("directional_futures_limit")
    if total_risk_pct > SOURCE_LIMITS["max_aggregate_risk_pct"] + 1e-9:
        reasons.append("aggregate_risk_limit")
    if risk_reward_net is None or risk_reward_net < 1.5:
        reasons.append("risk_reward_below_1_5_after_costs")
    if liquidation_buffer is not None and distance + .01 >= liquidation_buffer:
        reasons.append("stop_near_estimated_liquidation")
    if quantity <= 0 or estimated_loss <= 0 or notional <= 0:
        reasons.append("insufficient_risk_or_liquidity_budget")
    if not all(math.isfinite(x) for x in (budget, notional, quantity, estimated_loss, reward_net, margin_needed, total_risk_pct)):
        raise RiskInputError("numeric_overflow")

    return {
        "status": "BLOCKED" if reasons else "REVIEW_ONLY",
        "risk_review_passed": not reasons,
        "reasons": reasons or ["Sınırlar içinde; bu değerlendirme işlem izni vermez."],
        "market": market, "symbol": symbol, "side": side,
        "paper_account_equity": round(equity, 4),
        "daily_realized_pnl": round(spot_daily_pnl if market == "spot" else futures_daily_pnl, 4),
        "risk_budget": round(budget, 6),
        "upstream_risk_multiplier": throttle,
        "estimated_position_notional": round(notional, 6),
        "estimated_quantity": quantity, "estimated_loss_with_costs": round(estimated_loss, 6),
        "estimated_round_trip_fee": round(notional * fee_pct, 6),
        "estimated_round_trip_slippage": round(notional * slippage_pct, 6),
        "estimated_one_period_funding_reserve": round(notional * funding_rate, 6),
        "estimated_margin": round(margin_needed, 6),
        "net_risk_reward": round(risk_reward_net, 4) if risk_reward_net is not None else None,
        "estimated_aggregate_risk_pct": round(total_risk_pct, 4),
        "liquidation_proxy_distance_pct": round(liquidation_buffer * 100, 3) if liquidation_buffer is not None else None,
        "limits": SOURCE_LIMITS,
        "assumptions": [
            "Spot positions estimated at full market value; Futures existing positions at full remaining isolated margin.",
            "Funding estimate reserves one period of the observed absolute rate, not a guaranteed future funding payment.",
            "Liquidation distance is a rough maintenance-margin proxy, never Binance liquidation price.",
            "Orderbook depth, historical performance, and stops cannot guarantee realized fills.",
        ],
        "risk_approved": False,
        "paper_execution_permitted": False,
        "real_exchange_orders": False,
        "execution": "disabled",
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
