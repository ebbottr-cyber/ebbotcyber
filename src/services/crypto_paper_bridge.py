"""Strict read-only bridge for the EXISTING Trading Office Spot/Futures ledgers.

No duplicated balances, new ledger, execution authority, secret exposure or
POST request. The Trading Office /paper/* write endpoints are intentionally
NOT proxyable. Independent asynchronous views may race; reports are research
snapshots and may NEVER be used to authorize an order.
"""
from __future__ import annotations

import asyncio
import json
import math
import re
from datetime import datetime, timezone
from typing import Any

import httpx

from src.services.crypto_office_bridge import _connection_settings

_ALLOWED = {
    "spot-account": "/api/v1/paper/account",
    "spot-portfolio": "/api/v1/paper/portfolio",
    "futures-account": "/api/v1/paper/futures/account",
    "history": "/api/v1/paper/history",
    "performance": "/api/v1/paper/performance",
}
_PAIR = re.compile(r"^[A-Z0-9]{2,20}/(?:USDT|USDC|BTC|ETH)(?::USDT)?$")
_FUTURES_PAIR = re.compile(r"^[A-Z0-9]{2,20}/USDT(?::USDT)?$")
_ID = re.compile(r"^[a-zA-Z0-9_.:-]{1,100}$")
MAX_RESPONSE_BYTES = 2_000_000


class PaperReadError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _obj(v: Any, code: str = "invalid_paper_ledger") -> dict:
    if not isinstance(v, dict):
        raise PaperReadError(code)
    return v


def _array(v: Any, *, maximum: int = 500) -> list:
    if not isinstance(v, list) or len(v) > maximum:
        raise PaperReadError("invalid_paper_ledger")
    return v


def _num(v: Any, *, positive: bool = False, nonnegative: bool = False) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise PaperReadError("invalid_paper_ledger")
    try:
        out = float(v)
    except (TypeError, OverflowError, ValueError):
        raise PaperReadError("invalid_paper_ledger") from None
    if not math.isfinite(out) or (positive and out <= 0) or (nonnegative and out < 0):
        raise PaperReadError("invalid_paper_ledger")
    return out


def _optional(v: Any, *, nonnegative: bool = False) -> float | None:
    return None if v is None else _num(v, nonnegative=nonnegative)


def _integer(v: Any, *, minimum: int = 0) -> int:
    if type(v) is not int or v < minimum:
        raise PaperReadError("invalid_paper_ledger")
    return v


def _timestamp(v: Any) -> str:
    if not isinstance(v, str) or len(v) > 42:
        raise PaperReadError("invalid_paper_ledger")
    try:
        t = datetime.fromisoformat(v.replace("Z", "+00:00"))
        if t.tzinfo is None or t.utcoffset() is None or t.timestamp() > datetime.now(timezone.utc).timestamp() + 300:
            raise ValueError()
        return t.isoformat()
    except (TypeError, ValueError, OverflowError, OSError):
        raise PaperReadError("invalid_paper_ledger") from None


def _pair(v: Any, market: str) -> str:
    if not isinstance(v, str) or not (_FUTURES_PAIR if market == "futures" else _PAIR).fullmatch(v):
        raise PaperReadError("wrong_market_identity")
    return v


def _money_close(a: float, b: float) -> bool:
    return abs(a - b) <= max(0.001, max(abs(a), abs(b)) * 1e-7)


def validate_spot_ledger(raw: Any) -> dict:
    d = _obj(raw)
    if d.get("mode") != "paper_only" or d.get("persistence") != "sqlite_local_persistent":
        raise PaperReadError("unsafe_paper_mode")
    cash = _num(d.get("cash"), nonnegative=True)
    realized = _num(d.get("realized_pnl"))
    initial = _num(d.get("starting_cash"), positive=True)
    orders = _array(d.get("orders"), maximum=6000)
    if _integer(d.get("order_count")) != len(orders):
        raise PaperReadError("incomplete_paper_ledger")
    clean_orders = []
    ids: set[str] = set()
    for r in orders:
        row = _obj(r)
        identifier = row.get("id")
        if not isinstance(identifier, str) or not _ID.fullmatch(identifier) or identifier in ids:
            raise PaperReadError("invalid_paper_ledger")
        ids.add(identifier)
        symbol = _pair(row.get("symbol"), "spot")
        side = row.get("side")
        if side not in ("BUY", "SELL") or row.get("status") != "SIMULATED":
            raise PaperReadError("unsafe_paper_mode")
        qty = _num(row.get("quantity"), positive=True)
        price = _num(row.get("reference_price"), positive=True)
        notional = _num(row.get("notional"), positive=True)
        if not _money_close(qty * price, notional):
            raise PaperReadError("invalid_paper_ledger")
        fee = _num(row.get("fee"), nonnegative=True)
        realized_trade = _num(row.get("realized_pnl"))
        created = _timestamp(row.get("created_at"))
        clean_orders.append({
            "id": identifier, "symbol": symbol, "side": side,
            "quantity": qty, "price": price, "notional": notional,
            "fee": fee, "realized_pnl": realized_trade,
            "status": "SIMULATED", "created_at": created, "market": "spot",
        })
    positions = _array(d.get("positions"), maximum=300)
    cleaned = []
    symbols: set[str] = set()
    for item in positions:
        row = _obj(item)
        symbol = _pair(row.get("symbol"), "spot")
        if symbol in symbols:
            raise PaperReadError("invalid_paper_ledger")
        symbols.add(symbol)
        cleaned.append({
            "symbol": symbol,
            "quantity": _num(row.get("quantity"), positive=True),
            "average_price": _num(row.get("average_price"), positive=True),
        })
    return {
        "mode": "paper_only", "market": "spot",
        "cash": cash, "starting_cash": initial,
        "realized_pnl": realized,
        "positions": cleaned, "orders": clean_orders,
        "order_count": len(clean_orders),
    }


def validate_spot_portfolio(raw: Any, account: dict) -> dict:
    d = _obj(raw)
    if d.get("mode") != "paper_only" or d.get("market") != "spot":
        raise PaperReadError("wrong_market_identity")
    cash = _num(d.get("cash"), nonnegative=True)
    if not _money_close(cash, account["cash"]):
        raise PaperReadError("paper_account_changed")
    complete = d.get("valuation_complete")
    if type(complete) is not bool:
        raise PaperReadError("invalid_paper_ledger")
    positions = _array(d.get("positions"), maximum=300)
    if {p.get("symbol") for p in positions if isinstance(p, dict)} != {p["symbol"] for p in account["positions"]}:
        raise PaperReadError("paper_account_changed")
    clean_positions = []
    all_marked = True
    market_sum = 0.0
    for item in positions:
        row = _obj(item)
        symbol = _pair(row.get("symbol"), "spot")
        quantity = _num(row.get("quantity"), positive=True)
        average = _num(row.get("average_price"), positive=True)
        a = next((p for p in account["positions"] if p["symbol"] == symbol), None)
        if not a or not _money_close(quantity, a["quantity"]) or not _money_close(average, a["average_price"]):
            raise PaperReadError("paper_account_changed")
        mark = _optional(row.get("mark_price"))
        upnl = _optional(row.get("unrealized_pnl"))
        value = _optional(row.get("market_value"), nonnegative=True)
        if mark is None or mark <= 0 or upnl is None or value is None:
            if not (mark is None and upnl is None and value is None):
                raise PaperReadError("invalid_paper_ledger")
            all_marked = False
        else:
            if not _money_close(quantity * mark, value):
                raise PaperReadError("invalid_paper_ledger")
            market_sum += value
        clean_positions.append({
            "market": "spot", "symbol": symbol, "side": "BUY",
            "quantity": quantity, "average_price": average,
            "mark_price": mark, "unrealized_pnl": upnl,
            "notional": value,
        })
    if complete != all_marked:
        raise PaperReadError("invalid_paper_ledger")
    equity = _optional(d.get("equity"), nonnegative=True)
    unrealized = _optional(d.get("unrealized_pnl"))
    if complete:
        if equity is None or unrealized is None or not _money_close(equity, cash + market_sum):
            raise PaperReadError("invalid_paper_ledger")
    elif equity is not None or unrealized is not None:
        raise PaperReadError("incomplete_valuation")
    return {
        "market": "spot", "mode": "paper_only", "cash": cash,
        "equity": equity, "realized_pnl": _num(d.get("realized_pnl")),
        "unrealized_pnl": unrealized, "valuation_complete": complete,
        "positions": clean_positions, "order_count": account["order_count"],
    }


def validate_futures_account(raw: Any) -> dict:
    d = _obj(raw)
    if d.get("mode") != "paper_only" or d.get("market") != "futures":
        raise PaperReadError("wrong_market_identity")
    wallet = _num(d.get("wallet_balance"), nonnegative=True)
    realized = _num(d.get("realized_pnl"))
    margin = _num(d.get("used_initial_margin"), nonnegative=True)
    complete = d.get("valuation_complete")
    if type(complete) is not bool:
        raise PaperReadError("invalid_paper_ledger")
    equity = _optional(d.get("equity"), nonnegative=True)
    upnl = _optional(d.get("unrealized_pnl"))
    positions = _array(d.get("positions"), maximum=300)
    seen: set[str] = set()
    clean_positions = []
    sum_margin = 0.0
    for item in positions:
        p = _obj(item)
        symbol = _pair(p.get("symbol"), "futures")
        if symbol in seen or p.get("side") not in ("LONG", "SHORT"):
            raise PaperReadError("invalid_paper_ledger")
        seen.add(symbol)
        qty = _num(p.get("quantity"), positive=True)
        entry = _num(p.get("entry_price"), positive=True)
        leverage = _integer(p.get("leverage"), minimum=1)
        if leverage > 5:
            raise PaperReadError("invalid_paper_ledger")
        pos_margin = _num(p.get("margin"), nonnegative=True)
        sum_margin += pos_margin
        mark = _optional(p.get("mark_price"))
        pnl = _optional(p.get("unrealized_pnl"))
        notional = _optional(p.get("notional"), nonnegative=True)
        if mark is None or mark <= 0 or pnl is None or notional is None:
            if not (mark is None and pnl is None and notional is None):
                raise PaperReadError("invalid_paper_ledger")
        elif not _money_close(qty * mark, notional):
            raise PaperReadError("invalid_paper_ledger")
        clean_positions.append({
            "market": "futures", "symbol": symbol, "side": p["side"],
            "quantity": qty, "entry_price": entry, "leverage": leverage,
            "margin": pos_margin, "mark_price": mark, "notional": notional,
            "unrealized_pnl": pnl,
            "funding_paid": _num(p.get("funding_paid")),
            "entry_fee": _num(p.get("entry_fee"), nonnegative=True),
            "opened_at": _timestamp(p.get("opened_at")),
            "estimated_liquidation_price": _optional(p.get("estimated_liquidation_price"), nonnegative=True),
        })
    if not _money_close(sum_margin, margin):
        raise PaperReadError("invalid_paper_ledger")
    all_marked = all(p["mark_price"] is not None for p in clean_positions)
    if complete != all_marked:
        raise PaperReadError("invalid_paper_ledger")
    if complete:
        if equity is None or upnl is None or not _money_close(wallet + margin + upnl, equity):
            raise PaperReadError("invalid_paper_ledger")
    elif equity is not None or upnl is not None:
        raise PaperReadError("incomplete_valuation")
    trades = _array(d.get("trades"), maximum=100)
    clean_trades = []
    for row_raw in trades:
        row = _obj(row_raw)
        sym = _pair(row.get("symbol"), "futures")
        action = row.get("action")
        if action not in ("OPEN", "CLOSE", "LIQUIDATION", "FUNDING") or row.get("side") not in ("LONG", "SHORT"):
            raise PaperReadError("invalid_paper_ledger")
        clean_trades.append({
            "id": str(row.get("id", ""))[:100], "symbol": sym,
            "market": "futures", "action": action, "side": row["side"],
            "quantity": _num(row.get("quantity"), positive=True),
            "price": _num(row.get("price"), positive=True),
            "fee": _num(row.get("fee"), nonnegative=True),
            "realized_pnl": _num(row.get("realized_pnl")),
            "leverage": _integer(row.get("leverage"), minimum=1),
            "created_at": _timestamp(row.get("created_at")),
        })
    return {
        "mode": "paper_only", "market": "futures",
        "wallet_balance": wallet, "equity": equity,
        "used_initial_margin": margin,
        "realized_pnl": realized, "unrealized_pnl": upnl,
        "valuation_complete": complete, "positions": clean_positions,
        "trades": clean_trades,
        "daily_risk": d.get("daily_risk") if isinstance(d.get("daily_risk"), dict) else None,
    }


def validate_history(raw: Any, limit: int) -> dict:
    d = _obj(raw)
    if d.get("mode") != "paper_only" or _integer(d.get("count")) != len(_array(d.get("events"), maximum=limit)):
        raise PaperReadError("invalid_paper_ledger")
    rows = []
    for item in d["events"]:
        row = _obj(item)
        if row.get("market") not in ("spot", "futures"):
            raise PaperReadError("wrong_market_identity")
        source = row.get("source")
        if source not in ("spot_ledger", "futures_ledger", "trade_lifecycle"):
            raise PaperReadError("invalid_paper_ledger")
        if source == "spot_ledger" and row["market"] != "spot" or source == "futures_ledger" and row["market"] != "futures":
            raise PaperReadError("wrong_market_identity")
        price = _optional(row.get("price"))
        if price is not None and price <= 0:
            raise PaperReadError("invalid_paper_ledger")
        event_pnl = _num(row.get("event_pnl"))
        created_at = _timestamp(row.get("created_at"))
        rows.append({
            "id": str(row.get("id", ""))[:100],
            "market": row["market"], "source": source,
            "symbol": _pair(row.get("symbol"), row["market"]),
            "action": str(row.get("action") or row.get("side") or row.get("status") or "EVENT")[:28],
            "created_at": created_at, "price": price,
            "fee": _optional(row.get("fee"), nonnegative=True),
            "event_pnl": event_pnl,
        })
    return {"mode": "paper_only", "events": rows, "count": len(rows)}


def validate_performance(raw: Any) -> dict:
    d = _obj(raw)
    result = {}
    for period in ("daily", "weekly", "monthly"):
        item = _obj(d.get(period))
        result[period] = {
            "realized_net_pnl": _num(item.get("realized_net_pnl")),
            "event_count": _integer(item.get("event_count")),
            "since_utc": _timestamp(item.get("since_utc")),
        }
    if not isinstance(d.get("sources"), dict):
        raise PaperReadError("invalid_paper_ledger")
    return result


async def _get(dataset: str, *, limit: int = 100) -> dict:
    """No POST/PUT/DELETE. Fixed GET allowlist and authenticated localhost-only upstream."""
    if dataset not in _ALLOWED or type(limit) is not int or not 1 <= limit <= 500:
        raise PaperReadError("invalid_parameters")
    path = _ALLOWED[dataset]
    params = {"limit": limit} if dataset == "history" else None
    try:
        base, secret = _connection_settings()
    except Exception as exc:
        raise PaperReadError("paper_service_unavailable") from exc
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(25.0, connect=3.0),
            trust_env=False, follow_redirects=False,
        ) as client:
            async with client.stream(
                "GET", base + path, params=params,
                headers={"X-API-Key": secret, "Accept": "application/json"},
            ) as response:
                if response.status_code != 200 or "application/json" not in response.headers.get("content-type", "").lower():
                    raise PaperReadError("paper_service_unavailable")
                data = bytearray()
                async for block in response.aiter_bytes():
                    data.extend(block)
                    if len(data) > MAX_RESPONSE_BYTES:
                        raise PaperReadError("oversized_paper_response")
                try:
                    decoded = json.loads(data)
                except (TypeError, ValueError) as exc:
                    raise PaperReadError("invalid_paper_ledger") from exc
                return _obj(decoded)
    except PaperReadError:
        raise
    except (httpx.HTTPError, OSError, ValueError) as exc:
        raise PaperReadError("paper_service_unavailable") from exc


async def read_paper_summary() -> dict:
    """Read source-of-truth ledgers; never fabricate a new EBBot virtual account."""
    # All reads are GET. Sequential Spot snapshots permit cash/position reconciliation.
    spot_account = validate_spot_ledger(await _get("spot-account"))
    spot_portfolio = validate_spot_portfolio(await _get("spot-portfolio"), spot_account)
    futures = validate_futures_account(await _get("futures-account"))
    performance = validate_performance(await _get("performance"))
    total_equity = (spot_portfolio["equity"] + futures["equity"]
                    if spot_portfolio["equity"] is not None and futures["equity"] is not None
                    else None)
    if total_equity is not None and not math.isfinite(total_equity):
        raise PaperReadError("invalid_paper_ledger")
    return {
        "mode": "paper_only", "source": "Trading Office existing SQLite ledgers",
        "spot": spot_portfolio, "futures": futures,
        "performance": performance,
        "combined_equity": total_equity,
        "valuation_complete": total_equity is not None,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "safety": {
            "orders_placed": False, "paper_execution_permitted": False,
            "real_exchange_orders": False, "execution": "disabled",
        },
        "note": "Bağımsız kaynak GET anlık görüntüleri; işlem için atomik risk onayı değildir.",
    }


async def read_paper_history(market: str | None = None, limit: int = 100) -> dict:
    if market not in (None, "spot", "futures") or type(limit) is not int or not 1 <= limit <= 200:
        raise PaperReadError("invalid_parameters")
    # Filter locally; upstream returns most recent events across markets.
    history = validate_history(await _get("history", limit=limit), limit)
    if market is not None:
        history["events"] = [r for r in history["events"] if r["market"] == market]
        history["count"] = len(history["events"])
    return {
        **history, "market_filter": market,
        "source": "Trading Office existing SQLite ledgers",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "safety": {
            "orders_placed": False, "paper_execution_permitted": False,
            "real_exchange_orders": False, "execution": "disabled",
        },
    }
