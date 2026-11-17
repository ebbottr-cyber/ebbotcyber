"""EBBot crypto-only risk preflight.

Admin-only, independently calculated against trusted paper ledger and Binance
data. No endpoint here can create a Spot/Futures Paper order or live exchange order.
A REVIEW_ONLY result is not approval and never carries an execution token.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from api.v1.endpoints.crypto_office import require_crypto_admin
from src.services.crypto_risk_engine import RiskInputError, SOURCE_LIMITS
from src.services.crypto_risk_gateway import review_crypto_risk
from src.services.crypto_risk_audit import (
    RiskAuditError, record_risk_review, recent_risk_reviews,
)

router = APIRouter(dependencies=[Depends(require_crypto_admin)])


class CryptoRiskProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    market: Literal["spot", "futures"]
    symbol: str = Field(min_length=5, max_length=26, pattern=r"^[A-Z0-9]{2,20}/USDT$")
    side: Literal["BUY", "SELL"]
    entry_price: float = Field(gt=0, allow_inf_nan=False)
    stop_price: float = Field(gt=0, allow_inf_nan=False)
    take_profit_price: float = Field(gt=0, allow_inf_nan=False)
    risk_percent: float = Field(default=0.5, gt=0, le=2.0, allow_inf_nan=False)
    leverage: int = Field(default=1, ge=1, le=5, strict=True)


@router.get("/limits", summary="Fixed conservative crypto preflight limits")
async def crypto_risk_limits():
    return JSONResponse({
        "limits": SOURCE_LIMITS,
        "mode": "risk_research_only", "risk_approved": False,
        "paper_execution_permitted": False, "real_exchange_orders": False,
    }, headers={"Cache-Control": "private, no-store"})


@router.post("/review", summary="Manually run mandatory independent risk preflight")
async def crypto_risk_review(proposal: CryptoRiskProposal):
    payload = proposal.model_dump()
    try:
        result = await review_crypto_risk(payload)
    except RiskInputError as exc:
        code = 422 if exc.code.startswith("invalid_") or exc.code in {
            "spot_short_forbidden", "unsupported_currency",
        } else 503
        raise HTTPException(
            status_code=code,
            detail={"error": exc.code, "message": "Kripto risk bilgileri eksik veya geçersiz. İşlem kapalı."},
        ) from exc
    try:
        audit_id = record_risk_review(payload, result)
    except RiskAuditError as exc:
        raise HTTPException(
            status_code=503,
            detail={"error": "risk_audit_unavailable", "message": "Risk değerlendirmesi kaydedilemedi. İşlem kapalı."},
        ) from exc
    return JSONResponse(
        {**result, "audit_id": audit_id},
        headers={"Cache-Control": "private, no-store"},
    )


@router.get("/history", summary="Read-only audited hypothetical risk preflights")
async def crypto_risk_history(limit: int = Query(30, ge=1, le=100)):
    try:
        result = recent_risk_reviews(limit)
    except RiskAuditError as exc:
        raise HTTPException(
            status_code=503,
            detail={"error": "risk_audit_unavailable", "message": "Risk geçmişi güvenle alınamadı."},
        ) from exc
    return JSONResponse(result, headers={"Cache-Control": "private, no-store"})
