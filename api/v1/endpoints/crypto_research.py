"""EBBot research-only crypto API.

Separate from stock/crypto trade routes. An analysis is intentionally POST:
the upstream GET /agents/analyze appends research journal records.
Never automatically schedule it or turn it into Paper positions.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api.v1.endpoints.crypto_office import require_crypto_admin
from src.services.crypto_research_audit import CryptoAuditError, recent_decisions
from src.services.crypto_research_bridge import (
    CryptoResearchError,
    analyze,
    signals,
    weights,
    strategies,
    strategy_signal,
)

router = APIRouter(dependencies=[Depends(require_crypto_admin)])


class AnalysisRequest(BaseModel):
    market: Literal["spot", "futures"] = "spot"
    symbol: str = Field(default="BTC/USDT", min_length=3, max_length=26)
    timeframe: Literal["1m", "5m", "15m", "1h", "4h", "1d"] = "1h"


class StrategyRequest(AnalysisRequest):
    strategy: Literal[
        "scalping", "intraday", "swing", "trend_following",
        "mean_reversion", "momentum", "breakout",
    ]


def _error(exc: CryptoResearchError) -> HTTPException:
    status = {
        "invalid_parameters": 422,
        "not_configured": 503,
        "upstream_unavailable": 503,
        "market_data_unavailable": 503,
        "stale_market_data": 503,
        "snapshot_mismatch": 503,
    }.get(exc.code, 502)
    return HTTPException(
        status_code=status,
        detail={"error": exc.code, "message": "Kripto araştırma verileri güvenle doğrulanamadı."},
    )


def _response(value: dict) -> JSONResponse:
    return JSONResponse(content=value, headers={"Cache-Control": "private, no-store"})


@router.get("/strategies", summary="Seven registered crypto research strategies")
async def catalog():
    try:
        return _response(await strategies())
    except CryptoResearchError as exc:
        raise _error(exc) from exc


@router.get("/signals", summary="Read-only persistent research signal journal")
async def signal_journal(
    market: Literal["spot", "futures"] | None = None,
    limit: int = Query(50, ge=1, le=100),
):
    try:
        return _response(await signals(market, limit))
    except CryptoResearchError as exc:
        raise _error(exc) from exc


@router.get("/weights", summary="Read-only weights from closed research outcomes")
async def agent_weights(min_samples: int = Query(10, ge=1, le=500)):
    try:
        return _response(await weights(min_samples))
    except CryptoResearchError as exc:
        raise _error(exc) from exc


@router.post("/analyze", summary="Manually trigger deterministic analysis and research-journal entry")
async def run_agent_analysis(payload: AnalysisRequest):
    try:
        return _response(await analyze(payload.market, payload.symbol, payload.timeframe))
    except CryptoResearchError as exc:
        raise _error(exc) from exc


@router.post("/strategy", summary="Manually calculate a research-only strategy signal")
async def evaluate_crypto_strategy(payload: StrategyRequest):
    try:
        return _response(await strategy_signal(
            payload.market, payload.symbol, payload.timeframe, payload.strategy,
        ))
    except CryptoResearchError as exc:
        raise _error(exc) from exc



@router.get("/decisions", summary="Durable audit of ALL manually executed crypto research decisions")
async def decision_audit(limit: int = Query(30, ge=1, le=100)):
    try:
        return _response(recent_decisions(limit))
    except CryptoAuditError as exc:
        raise HTTPException(
            status_code=503,
            detail={"error": exc.args[0], "message": "Kripto karar kayıtları güvenli biçimde okunamadı."},
        ) from exc
