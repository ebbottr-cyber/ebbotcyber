"""Trusted EBBot risk inputs from Trading Office paper ledger and Binance public feeds.

All accesses are server-side, read-only and restricted to the isolated local
service. Never accept caller supplied balances, paper records or funding rates.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any

import httpx

from src.services.crypto_office_bridge import _connection_settings, read_crypto_dashboard
from src.services.crypto_risk_engine import RiskInputError, evaluate_risk
from src.services.crypto_spot_bridge import spot_data
from src.services.crypto_futures_bridge import futures_data


async def _paper_account() -> dict:
    try:
        base, key = _connection_settings()
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(15.0, connect=3.0),
            trust_env=False, follow_redirects=False,
        ) as client:
            async with client.stream("GET", base + "/api/v1/paper/account", headers={
                "X-API-Key": key, "Accept": "application/json",
            }) as response:
                if response.status_code != 200 or "application/json" not in response.headers.get("content-type", ""):
                    raise RiskInputError("spot_ledger_unavailable")
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    data.extend(chunk)
                    if len(data) > 2_000_000:
                        raise RiskInputError("spot_ledger_oversized")
                try:
                    raw = json.loads(data)
                except (TypeError, ValueError) as exc:
                    raise RiskInputError("spot_ledger_unavailable") from exc
                if not isinstance(raw, dict) or raw.get("mode") != "paper_only":
                    raise RiskInputError("spot_ledger_unavailable")
                return raw
    except RiskInputError:
        raise
    except (httpx.HTTPError, OSError, ValueError) as exc:
        raise RiskInputError("spot_ledger_unavailable") from exc


def _valid_time(value: Any) -> datetime:
    if not isinstance(value, str):
        raise RiskInputError("spot_ledger_invalid")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is None or result.utcoffset() is None:
            raise ValueError()
        return result.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        raise RiskInputError("spot_ledger_invalid") from None


def spot_daily_from_ledger(account: dict, spot_view: dict) -> float:
    """UTC realized daily PnL: opening BUY fee + SELL realized PnL.

    The ledger's SELL realized_pnl already incorporates closing fee and
    purchase cost basis; do not deduct the SELL fee a second time.
    """
    if not isinstance(account, dict) or not isinstance(spot_view, dict):
        raise RiskInputError("spot_ledger_invalid")
    if account.get("mode") != "paper_only" or spot_view.get("mode") != "paper_only":
        raise RiskInputError("spot_ledger_invalid")
    if not isinstance(account.get("orders"), list) or len(account["orders"]) > 10_000:
        raise RiskInputError("spot_ledger_invalid")
    cash = account.get("cash")
    view_cash = spot_view.get("cash")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in (cash, view_cash)):
        raise RiskInputError("spot_ledger_invalid")
    if not math.isfinite(cash) or not math.isfinite(view_cash) or abs(cash - view_cash) > max(0.001, abs(view_cash) * 1e-7):
        raise RiskInputError("spot_ledger_not_reconciled")
    today = datetime.now(timezone.utc).date()
    total = 0.0
    for order in account["orders"]:
        if not isinstance(order, dict) or order.get("side") not in ("BUY", "SELL"):
            raise RiskInputError("spot_ledger_invalid")
        created = _valid_time(order.get("created_at"))
        if created > datetime.now(timezone.utc):
            raise RiskInputError("spot_ledger_invalid")
        for field in ("fee", "realized_pnl"):
            value = order.get(field)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise RiskInputError("spot_ledger_invalid")
            if not math.isfinite(value):
                raise RiskInputError("spot_ledger_invalid")
        if order["fee"] < 0:
            raise RiskInputError("spot_ledger_invalid")
        if created.date() == today:
            total += (-order["fee"] if order["side"] == "BUY" else order["realized_pnl"])
            if not math.isfinite(total):
                raise RiskInputError("spot_ledger_invalid")
    return total


async def read_risk_facts(proposal: dict) -> tuple[dict, float, dict, dict, dict | None]:
    """Read coherent enough source data for an advisory risk preflight.

    Coherence is intentionally conservative: portfolio snapshots and ledger
    cash must agree, prices must be individually verified and current.
    Paper mutations in the source office may race these reads; for that
    reason the result NEVER grants execution permission.
    """
    try:
        dashboard = await read_crypto_dashboard()
        spot_view = dashboard.get("portfolio", {}).get("spot")
        account = await _paper_account()
        spot_daily = spot_daily_from_ledger(account, spot_view)
        market = proposal.get("market")
        symbol = proposal.get("symbol")
        if market == "spot":
            ticker = await spot_data("ticker", symbol)
            depth = await spot_data("orderbook", symbol, limit=20)
            funding = None
        elif market == "futures":
            ticker = await futures_data("ticker", symbol)
            depth = await futures_data("orderbook", symbol, limit=20)
            funding = await futures_data("funding", symbol)
        else:
            raise RiskInputError("invalid_request")
        return dashboard, spot_daily, ticker, depth, funding
    except RiskInputError:
        raise
    except Exception as exc:
        # Don't include upstream response bodies or secrets in error output.
        raise RiskInputError("risk_sources_unavailable") from exc


async def review_crypto_risk(proposal: dict) -> dict:
    facts = await read_risk_facts(proposal)
    return evaluate_risk(proposal, *facts)
