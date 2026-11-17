"""Admin-only EBBot Paper account and history views — explicitly non-executable.

The Trading Office currently exposes independent POST endpoints that can
mutate its SQLite ledger without EBBot's risk engine. Until an upstream
atomic gate is deployed and verified, this router exposes ONLY GET.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from api.v1.endpoints.crypto_office import require_crypto_admin
from src.services.crypto_paper_bridge import (
    PaperReadError, read_paper_history, read_paper_summary,
)

from src.services.crypto_paper_v2_status import PaperV2StatusUnavailable, read_v2_status

router = APIRouter(dependencies=[Depends(require_crypto_admin)])


def _fail(exc: PaperReadError) -> HTTPException:
    return HTTPException(
        status_code=422 if exc.code == "invalid_parameters" else 503,
        detail={"error": exc.code, "message": "Paper Trading kaydı doğrulanamadı. İşlem yetkisi kapalı."},
    )


@router.get("/summary", summary="Existing Spot/Futures paper accounts, read only")
async def crypto_paper_summary():
    try:
        value = await read_paper_summary()
    except PaperReadError as exc:
        raise _fail(exc) from exc
    return JSONResponse(content=value, headers={"Cache-Control": "private, no-store"})


@router.get("/history", summary="Existing paper execution and funding history, read only")
async def crypto_paper_history(
    market: Literal["spot", "futures"] | None = None,
    limit: int = Query(100, ge=1, le=200),
):
    try:
        value = await read_paper_history(market, limit)
    except PaperReadError as exc:
        raise _fail(exc) from exc
    return JSONResponse(content=value, headers={"Cache-Control": "private, no-store"})



@router.get("/capabilities", summary="Upstream Paper V2 capability claims; never grants execution")
async def crypto_paper_capabilities():
    try:
        source = await read_v2_status()
    except PaperV2StatusUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "error": exc.code,
                "message": "Paper V2 güvenliği kaynakta doğrulanamadı. EBBot emirleri kapalı.",
            },
        ) from exc
    value = {
        "upstream_v2_present": True,
        "upstream_v2_opted_in": source["source_flag_claimed_enabled"],
        "source_state": source["source_state"],
        "source_claims_atomic_risk_gate": True,
        "readiness_verified": False,
        "ebbot_paper_execution_permitted": False,
        "real_exchange_orders": False,
        "execution": "disabled",
        "checked_at": source["checked_at"],
        "note": "Yalnız kaynak beyanı; bağımsız test ve dağıtım olmadan Paper V2 emir izni yok.",
    }
    return JSONResponse(content=value, headers={"Cache-Control": "private, no-store"})
