"""Read-only research endpoints: no signals, positions or order execution."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.config import get_config
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
