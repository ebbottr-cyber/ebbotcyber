"""Read-only research endpoints: no signals, positions or order execution."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.config import get_config
from src.auth import is_auth_enabled
from src.services.paper_journal_reporting import inspect_paper_journal_text
from src.services.strategy_lab_service import (
    BenchmarkDataUnavailable,
    analyze_configured_etf,
    eligible_etfs,
)


logger = logging.getLogger(__name__)
router = APIRouter()


class EtfBenchmarkRequest(BaseModel):
    asset_code: str = Field(min_length=6, max_length=6, pattern=r"^[0-9]{6}$")
    simulations: int = Field(default=500, ge=100, le=4000)


@router.get("/etfs", summary="ETF pool eligible for read-only timing research")
def list_eligible_etfs() -> dict:
    return {"items": eligible_etfs(get_config()), "research_only": True}


@router.post("/etf", summary="Compare existing ETF rotation to randomized trade timing")
def evaluate_etf_timing(request: EtfBenchmarkRequest) -> dict:
    try:
        return analyze_configured_etf(
            asset_code=request.asset_code,
            simulations=request.simulations,
            config=get_config(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"error": "invalid_params", "message": str(exc)}) from exc
    except BenchmarkDataUnavailable as exc:
        raise HTTPException(status_code=422, detail={"error": "unavailable_data", "message": str(exc)}) from exc
    except Exception:
        logger.exception("ETF strategy lab research evaluation failed")
        raise HTTPException(
            status_code=503,
            detail={"error": "research_unavailable", "message": "Research computation is temporarily unavailable"},
        ) from None


class PaperJournalInspectRequest(BaseModel):
    journal_jsonl: str = Field(min_length=1, max_length=524288)


@router.post("/paper/inspect", summary="Inspect an uploaded paper journal, without storing it")
def inspect_paper_journal(request: PaperJournalInspectRequest) -> dict:
    # Unlike other optional public research APIs, journal contents are
    # potentially private. Deny this route entirely if admin auth is off;
    # with auth enabled the normal /api/v1 middleware requires a session.
    if not is_auth_enabled():
        raise HTTPException(status_code=403, detail={
            "error": "auth_required", "message": "Enable admin authentication before inspecting paper journals",
        })
    try:
        return inspect_paper_journal_text(request.journal_jsonl)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={
            "error": "invalid_journal", "message": str(exc),
        }) from exc
