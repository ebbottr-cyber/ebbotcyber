# -*- coding: utf-8 -*-
"""Data capability and quality endpoints."""

from __future__ import annotations

import logging

from fastapi.responses import JSONResponse
from src.auth import COOKIE_NAME, is_auth_enabled, verify_session
from src.services.bist100_report_reader import (
    CoverageReportInvalid,
    CoverageReportUnavailable,
    load_configured_coverage_report,
)
from src.services.bist100_technical_report_reader import (
    TechnicalReportInvalid,
    TechnicalReportUnavailable,
    load_configured_technical_report,
)

from fastapi import APIRouter, Depends, HTTPException, Request

from api.deps import get_config_dep
from api.v1.schemas.common import ErrorResponse
from api.v1.schemas.data_capability import DataCapabilityOverviewResponse
from src.config import Config
from src.services.data_capability_service import DataCapabilityService

logger = logging.getLogger(__name__)

router = APIRouter()


def _overview_response(config: Config, *, runtime_scheduler: object = None) -> DataCapabilityOverviewResponse:
    try:
        payload = DataCapabilityService(
            config=config,
            runtime_scheduler=runtime_scheduler,
        ).get_overview()
        return DataCapabilityOverviewResponse.model_validate(payload)
    except Exception as exc:  # noqa: BLE001 - keep diagnostics fail-open at API boundary.
        logger.error("Failed to build data capability overview: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": "Failed to build data capability overview",
            },
        )


@router.get(
    "/overview",
    response_model=DataCapabilityOverviewResponse,
    responses={500: {"model": ErrorResponse}},
    summary="Get data capability overview",
    description="Return provider capabilities, dataset quality, and source priority without exposing secrets.",
)
def get_data_overview(
    request: Request,
    config: Config = Depends(get_config_dep),
) -> DataCapabilityOverviewResponse:
    """Return the canonical read-only data overview."""
    return _overview_response(
        config,
        runtime_scheduler=getattr(request.app.state, "runtime_scheduler_service", None),
    )


@router.get(
    "/capabilities",
    response_model=DataCapabilityOverviewResponse,
    responses={500: {"model": ErrorResponse}},
    summary="Get data provider capabilities",
    description="Alias of /data/overview for clients that only need capability metadata.",
)
def get_data_capabilities(
    request: Request,
    config: Config = Depends(get_config_dep),
) -> DataCapabilityOverviewResponse:
    """Return the data overview under the capability-oriented alias."""
    return _overview_response(
        config,
        runtime_scheduler=getattr(request.app.state, "runtime_scheduler_service", None),
    )


@router.get(
    "/bist100/coverage",
    summary="Read saved BIST100 Yahoo history coverage",
    description=(
        "Read-only access to an operator-configured historical report. "
        "Requires an authenticated admin session. Does not fetch prices or analyze stocks."
    ),
)
def get_bist100_coverage(request: Request):
    """Fail closed when admin auth is disabled; never expose server file paths."""
    if not is_auth_enabled():
        raise HTTPException(status_code=404, detail="BIST100 report is unavailable")
    session = request.cookies.get(COOKIE_NAME)
    if not session or not verify_session(session):
        raise HTTPException(status_code=401, detail="Admin login required")
    try:
        data = load_configured_coverage_report()
    except CoverageReportUnavailable as exc:
        raise HTTPException(status_code=404, detail="BIST100 report not configured") from exc
    except CoverageReportInvalid as exc:
        logger.warning("Configured BIST100 report failed validation")
        raise HTTPException(status_code=422, detail="BIST100 report failed validation") from exc
    return JSONResponse(
        content=data,
        headers={"Cache-Control": "no-store, private", "X-Content-Type-Options": "nosniff"},
    )


@router.get(
    "/bist100/technical-ranking",
    summary="Read saved BIST100 technical ranking",
    description=(
        "Serve only a pre-generated, operator-configured technical report. "
        "Requires admin authentication. Never queries SQLite, performs analyses, "
        "retrieves prices, or places orders."
    ),
)
def get_bist100_technical_ranking(request: Request):
    """Do not allow API callers to select local file paths or launch a scan."""
    if not is_auth_enabled():
        raise HTTPException(status_code=404, detail="BIST100 technical report is unavailable")
    session = request.cookies.get(COOKIE_NAME)
    if not session or not verify_session(session):
        raise HTTPException(status_code=401, detail="Admin login required")
    try:
        data = load_configured_technical_report()
    except TechnicalReportUnavailable as exc:
        raise HTTPException(status_code=404, detail="BIST100 technical report not configured") from exc
    except TechnicalReportInvalid as exc:
        logger.warning("Configured BIST100 technical report failed validation")
        raise HTTPException(status_code=422, detail="BIST100 technical report failed validation") from exc
    return JSONResponse(
        content=data,
        headers={"Cache-Control": "no-store, private", "X-Content-Type-Options": "nosniff"},
    )
