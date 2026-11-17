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
    read_paper_v2_capabilities,
)

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



@router.get("/capabilities", summary="Paper V2 source availability; never grants execution")
async def crypto_paper_capabilities():
    value = await read_paper_v2_capabilities()
    return JSONResponse(content=value, headers={"Cache-Control": "private, no-store"})
