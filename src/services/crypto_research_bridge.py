"""EBBot crypto research gateway: nine deterministic agents and strategy journal.

Source: AI Multi-Market Trading Office /agents/analyze,
/agents/signals, /agents/weights, /strategies and /strategies/{id}/signal.
Intentional analyses persist research-only journal entries on the upstream,
so they are NOT polled or triggered automatically. No trade endpoints.
"""
from __future__ import annotations

import json
import math
import re
import time
from datetime import datetime, timezone
from typing import Any, Literal

import httpx

from src.services.crypto_office_bridge import _connection_settings
from src.services.crypto_spot_bridge import spot_data
from src.services.crypto_futures_bridge import futures_data, normalize_pair

Market = Literal["spot", "futures"]
FRAMES = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}
STRATEGIES = frozenset({
    "scalping", "intraday", "swing", "trend_following",
    "mean_reversion", "momentum", "breakout",
})
AGENTS = frozenset({
    "trend", "scalping", "momentum", "mean_reversion",
    "breakout", "intraday", "swing", "volume", "orderbook",
})
ACTIONS = frozenset({"BUY", "SELL", "HOLD"})
PAIR = re.compile(r"^[A-Z0-9]{2,20}/(?:USDT|USDC|BTC|ETH)$")
MAX_BYTES = 700_000


class CryptoResearchError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _num(value: Any, *, lo: float | None = None, hi: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CryptoResearchError("invalid_research")
    try:
        val = float(value)
    except (OverflowError, TypeError, ValueError) as exc:
        raise CryptoResearchError("invalid_research") from exc
    if not math.isfinite(val) or lo is not None and val < lo or hi is not None and val > hi:
        raise CryptoResearchError("invalid_research")
    return val


def _int(value: Any, *, min_value: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < min_value:
        raise CryptoResearchError("invalid_research")
    return value


def _symbol(market: str, symbol: str) -> tuple[str, str]:
    if market not in ("spot", "futures") or not isinstance(symbol, str):
        raise CryptoResearchError("invalid_parameters")
    pair = symbol.strip().upper()
    if market == "futures":
        try:
            _, contract, _ = normalize_pair(pair)
            return pair, contract
        except Exception as exc:
            raise CryptoResearchError("invalid_parameters") from exc
    if not PAIR.fullmatch(pair):
        raise CryptoResearchError("invalid_parameters")
    return pair, pair


def _frame(frame: str) -> str:
    if frame not in FRAMES:
        raise CryptoResearchError("invalid_parameters")
    return frame


def _no_orders(raw: Any, *, mode: str | None = None) -> dict:
    if not isinstance(raw, dict) or raw.get("orders_placed") is not False:
        raise CryptoResearchError("unsafe_research")
    if mode is not None and raw.get("mode") != mode:
        raise CryptoResearchError("unsafe_research")
    return raw


async def _get(path: str, params: dict[str, Any] | None = None) -> dict:
    # Never accept arbitrary endpoints, URLs, credentials, or user-provided paths.
    if not (
        path in {"/api/v1/agents/analyze", "/api/v1/agents/signals",
                 "/api/v1/agents/signals/summary", "/api/v1/agents/weights",
                 "/api/v1/strategies", "/api/v1/strategies/performance"}
        or re.fullmatch(r"/api/v1/strategies/(?:scalping|intraday|swing|trend_following|mean_reversion|momentum|breakout)/signal", path)
    ):
        raise CryptoResearchError("invalid_parameters")
    try:
        base, key = _connection_settings()
    except Exception as exc:
        raise CryptoResearchError("not_configured") from exc
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(35.0 if path.endswith("/analyze") else 15.0, connect=3.0),
            follow_redirects=False,
            trust_env=False,
        ) as client:
            async with client.stream(
                "GET", base + path, params=params or {},
                headers={"X-API-Key": key, "Accept": "application/json"},
            ) as response:
                if response.status_code == 400:
                    raise CryptoResearchError("invalid_parameters")
                if response.status_code in (429, 503):
                    raise CryptoResearchError("upstream_unavailable")
                if response.status_code != 200:
                    raise CryptoResearchError("upstream_unavailable")
                if "application/json" not in response.headers.get("content-type", "").lower():
                    raise CryptoResearchError("invalid_research")
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    data.extend(chunk)
                    if len(data) > MAX_BYTES:
                        raise CryptoResearchError("oversized_research")
                try:
                    result = json.loads(data)
                except (TypeError, ValueError) as exc:
                    raise CryptoResearchError("invalid_research") from exc
                if not isinstance(result, dict):
                    raise CryptoResearchError("invalid_research")
                return result
    except CryptoResearchError:
        raise
    except (httpx.HTTPError, OSError, ValueError) as exc:
        raise CryptoResearchError("upstream_unavailable") from exc


def _report(raw: Any, market: str, identity: str, timeframe: str, last_timestamp: int) -> dict:
    if not isinstance(raw, dict) or raw.get("market") != market or raw.get("symbol") != identity:
        raise CryptoResearchError("wrong_market_identity")
    if raw.get("timeframe") != timeframe or raw.get("execution") != "disabled" or raw.get("mode") != "research_only":
        raise CryptoResearchError("unsafe_research")
    if raw.get("data_source") != "Binance public market data":
        raise CryptoResearchError("wrong_market_identity")
    stamp = _int(raw.get("candle_timestamp"), min_value=1)
    # Preflight validated the same market, contract and candle.
    # Reject a different data snapshot rather than trusting a journaled recommendation.
    if stamp != last_timestamp:
        raise CryptoResearchError("snapshot_mismatch")
    if time.time() * 1000 - stamp > FRAMES[timeframe] * 3000 + 180_000:
        raise CryptoResearchError("stale_market_data")
    if stamp > time.time() * 1000 + 300_000:
        raise CryptoResearchError("future_market_data")
    last_price = _num(raw.get("last_close"), lo=0.0000001)
    if raw.get("action") not in ACTIONS:
        raise CryptoResearchError("invalid_research")
    confidence = _num(raw.get("confidence"), lo=0, hi=1)
    agreement = _num(raw.get("agreement"), lo=0, hi=1)
    if raw["action"] == "HOLD" and confidence != 0:
        raise CryptoResearchError("invalid_research")
    agents = raw.get("agents")
    if not isinstance(agents, list) or len(agents) != 9:
        raise CryptoResearchError("invalid_research")
    verified: list[dict[str, Any]] = []
    for a in agents:
        if not isinstance(a, dict) or a.get("agent") not in AGENTS or a.get("action") not in ACTIONS:
            raise CryptoResearchError("invalid_research")
        verified.append({
            "agent": a["agent"],
            "action": a["action"],
            "confidence": _num(a.get("confidence"), lo=0, hi=1),
            "rationale": str(a.get("rationale", ""))[:450],
            "regime_weight": _num(a.get("regime_weight"), lo=0, hi=10),
            "performance_weight": _num(a.get("performance_weight"), lo=0, hi=10),
        })
    if {a["agent"] for a in verified} != AGENTS:
        raise CryptoResearchError("invalid_research")
    votes = raw.get("votes")
    if not isinstance(votes, dict) or sum(_int(votes.get(n)) for n in ("buy", "sell", "hold")) != 9:
        raise CryptoResearchError("invalid_research")
    perf = raw.get("performance_weighting")
    if not isinstance(perf, dict) or perf.get("training") is not False:
        raise CryptoResearchError("unsafe_research")
    journal = raw.get("journal")
    if not isinstance(journal, dict) or not isinstance(journal.get("signals"), list):
        raise CryptoResearchError("invalid_research")
    _int(journal.get("recorded"))
    regime = raw.get("market_regime")
    regime_name = regime.get("name") if isinstance(regime, dict) else None
    context = raw.get("news_context")
    return {
        "market": market,
        "symbol": identity,
        "timeframe": timeframe,
        "action": raw["action"],
        "confidence": confidence,
        "agreement": agreement,
        "votes": {k: votes[k] for k in ("buy", "sell", "hold")},
        "agents": verified,
        "market_regime": str(regime_name)[:100] if regime_name is not None else None,
        "news_context": {
            "risk_level": str(context.get("risk_level", "unknown"))[:50],
            "article_count": _int(context.get("article_count", 0)),
        } if isinstance(context, dict) else {"risk_level": "unknown", "article_count": 0},
        "last_close": last_price,
        "candle_timestamp": stamp,
        "journal_recorded": journal["recorded"],
        "journal_note": "Araştırma günlüğü kaydı; gerçek veya sanal emir değildir.",
        "engine": "deterministic_ensemble",
        "training": False,
        "risk_approved": False,
        "execution": "disabled",
        "orders_placed": False,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


async def analyze(market: str, symbol: str, timeframe: str = "1h") -> dict:
    pair, identity = _symbol(market, symbol)
    frame = _frame(timeframe)
    # Preflight ensures Binance data are not missing/stale BEFORE triggering
    # the upstream GET /agents/analyze, which writes a research journal row.
    try:
        prices = await (
            spot_data("ohlcv", pair, frame, 250)
            if market == "spot" else futures_data("ohlcv", pair, frame, 250)
        )
    except Exception as exc:
        raise CryptoResearchError("market_data_unavailable") from exc
    if prices.get("quality") != "ok" or len(prices.get("candles", [])) < 60:
        raise CryptoResearchError("market_data_unavailable")
    last_ts = prices["last_candle_timestamp"]
    raw = await _get("/api/v1/agents/analyze", {
        "market": market,
        "symbol": identity,
        "timeframe": frame,
        "limit": 250,
        "include_orderbook": True,
    })
    return _report(raw, market, identity, frame, last_ts)


async def signals(market: str | None = None, limit: int = 50) -> dict:
    if market not in (None, "spot", "futures") or not 1 <= limit <= 100:
        raise CryptoResearchError("invalid_parameters")
    params: dict[str, Any] = {"limit": limit}
    if market is not None:
        params["market"] = market
    raw = _no_orders(await _get("/api/v1/agents/signals", params), mode="journal_only")
    rows = raw.get("signals")
    if not isinstance(rows, list) or len(rows) > limit:
        raise CryptoResearchError("invalid_research")
    valid = []
    for row in rows:
        if not isinstance(row, dict) or row.get("market") not in ("spot", "futures") or row.get("action") not in ("BUY", "SELL"):
            raise CryptoResearchError("invalid_research")
        if market is not None and row["market"] != market:
            raise CryptoResearchError("wrong_market_identity")
        raw_outcome = row.get("outcome")
        if raw_outcome not in (None, "WIN", "LOSS", "BREAKEVEN"):
            raise CryptoResearchError("invalid_research")
        entry = _num(row.get("entry_price"), lo=0.0000001)
        exit_price = _num(row["exit_price"], lo=0.0000001) if row.get("exit_price") is not None else None
        valid.append({
            "id": str(row.get("id", ""))[:80],
            "created_at": str(row.get("created_at", ""))[:40],
            "market": row["market"], "symbol": str(row.get("symbol", ""))[:32],
            "timeframe": str(row.get("timeframe", ""))[:8],
            "agent": str(row.get("agent", ""))[:40],
            "action": row["action"],
            "confidence": _num(row.get("confidence"), lo=0, hi=1),
            "entry_price": entry, "exit_price": exit_price,
            "outcome": raw_outcome,
            "pnl_pct": _num(row["pnl_pct"]) if row.get("pnl_pct") is not None else None,
            "strategy_name": str(row.get("strategy_name") or "")[:40],
        })
    return {
        "signals": valid, "count": len(valid),
        "total_matching": _int(raw.get("total_matching")),
        "market": market, "mode": "journal_only",
        "orders_placed": False, "execution": "disabled",
    }


async def weights(min_samples: int = 10) -> dict:
    if not 1 <= min_samples <= 500:
        raise CryptoResearchError("invalid_parameters")
    raw = _no_orders(await _get("/api/v1/agents/weights", {"min_samples": min_samples}))
    if raw.get("training") is not False or raw.get("method") != "closed_signal_outcomes_with_sample_shrinkage":
        raise CryptoResearchError("unsafe_research")
    names = raw.get("weights")
    if not isinstance(names, dict):
        raise CryptoResearchError("invalid_research")
    clean = {}
    for name, value in names.items():
        if name not in AGENTS:
            raise CryptoResearchError("invalid_research")
        clean[name] = _num(value, lo=.75, hi=1.25)
    return {"weights": clean, "min_samples": min_samples, "training": False,
            "method": "closed_signal_outcomes_with_sample_shrinkage", "orders_placed": False}


async def strategies() -> dict:
    raw = _no_orders(await _get("/api/v1/strategies"), mode="research_only")
    entries = raw.get("strategies")
    if not isinstance(entries, list) or len(entries) != len(STRATEGIES):
        raise CryptoResearchError("invalid_research")
    clean = []
    for item in entries:
        if not isinstance(item, dict) or item.get("name") not in STRATEGIES:
            raise CryptoResearchError("invalid_research")
        clean.append({"name": item["name"], "description": str(item.get("description", ""))[:250]})
    if {i["name"] for i in clean} != STRATEGIES:
        raise CryptoResearchError("invalid_research")
    return {"strategies": clean, "mode": "research_only", "orders_placed": False}


async def strategy_signal(market: str, symbol: str, timeframe: str, strategy: str) -> dict:
    pair, identity = _symbol(market, symbol)
    frame = _frame(timeframe)
    if strategy not in STRATEGIES:
        raise CryptoResearchError("invalid_parameters")
    # Source strategy endpoint has no journal write, but must still receive
    # recent, complete market candles. Preflight avoids stale analysis requests.
    try:
        prices = await (
            spot_data("ohlcv", pair, frame, 100)
            if market == "spot" else futures_data("ohlcv", pair, frame, 100)
        )
    except Exception as exc:
        raise CryptoResearchError("market_data_unavailable") from exc
    if prices.get("quality") != "ok" or len(prices.get("candles", [])) < 50:
        raise CryptoResearchError("market_data_unavailable")
    raw = await _get(f"/api/v1/strategies/{strategy}/signal", {
        "market": market, "symbol": identity, "timeframe": frame, "limit": 100,
    })
    if raw.get("market") != market or raw.get("execution") != "disabled":
        raise CryptoResearchError("unsafe_research")
    if raw.get("data_source") != "Binance public market data":
        raise CryptoResearchError("wrong_market_identity")
    signal = raw.get("signal")
    if not isinstance(signal, dict) or signal.get("strategy") != strategy or signal.get("symbol") != identity or signal.get("timeframe") != frame:
        raise CryptoResearchError("wrong_market_identity")
    if signal.get("action") not in ACTIONS:
        raise CryptoResearchError("invalid_research")
    stamp = signal.get("candle_timestamp")
    if stamp != prices["last_candle_timestamp"]:
        raise CryptoResearchError("snapshot_mismatch")
    for item in ("entry_reference", "stop_reference", "take_profit_reference"):
        if signal.get(item) is not None:
            _num(signal[item], lo=0.0000001)
    return {
        "market": market, "symbol": identity, "timeframe": frame,
        "strategy": strategy, "action": signal["action"],
        "confidence": _num(signal.get("confidence"), lo=0, hi=1),
        "rationale": str(signal.get("rationale", ""))[:450],
        "entry_reference": signal.get("entry_reference"),
        "stop_reference": signal.get("stop_reference"),
        "take_profit_reference": signal.get("take_profit_reference"),
        "risk_reward": _num(signal["risk_reward"], lo=0) if signal.get("risk_reward") is not None else None,
        "candle_timestamp": stamp, "risk_approved": False,
        "execution": "disabled", "orders_placed": False,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
