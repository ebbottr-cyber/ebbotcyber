# -*- coding: utf-8 -*-
"""Data capability and quality endpoints."""

from __future__ import annotations

from datetime import datetime
import logging
from zoneinfo import ZoneInfo

from src.services.bist100_universe import load_bist100_universe

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
from src.services.five_market_report_reader import (
    FiveMarketReportInvalid,
    FiveMarketReportUnavailable,
    load_configured_five_market_sample_report,
)
from src.services.four_market_progress_report_reader import (
    FourMarketProgressInvalid,
    FourMarketProgressUnavailable,
    load_configured_four_market_batch_progress,
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

@router.get(
    "/four-market/samples",
    summary="Read an operator-configured four-market historical sample report",
    description=(
        "Admin-only, pre-generated Yahoo sample report. Never scans markets, "
        "reads the user's SQLite database, fetches prices, or places orders."
    ),
)
def get_five_market_sample_report(request: Request):
    """Server file path comes only from the operator environment, never HTTP."""
    if not is_auth_enabled():
        raise HTTPException(status_code=404, detail="Four-market report unavailable")
    session = request.cookies.get(COOKIE_NAME)
    if not session or not verify_session(session):
        raise HTTPException(status_code=401, detail="Admin login required")
    try:
        report = load_configured_five_market_sample_report()
    except FiveMarketReportUnavailable as exc:
        raise HTTPException(status_code=404, detail="Four-market report not configured") from exc
    except FiveMarketReportInvalid as exc:
        logger.warning("Configured four-market sample report failed validation")
        raise HTTPException(status_code=422, detail="Four-market report failed validation") from exc
    return JSONResponse(
        content=report,
        headers={"Cache-Control": "no-store, private", "X-Content-Type-Options": "nosniff"},
    )

@router.get(
    "/four-market/universe/tr",
    summary="Read the source-dated public BIST100 equity roster",
    description=(
        "Return only the already cross-checked 100-member BIST100 quarterly "
        "snapshot. No SQLite, quote fetch, brokerage or trade operations. "
        "Login required when admin authentication is enabled."
    ),
)
def get_four_market_turkey_universe(request: Request):
    """Fail closed outside the verified BIST100 index-membership period."""
    if is_auth_enabled():
        session = request.cookies.get(COOKIE_NAME)
        if not session or not verify_session(session):
            raise HTTPException(status_code=401, detail="Admin login required")
    as_of = datetime.now(ZoneInfo("Europe/Istanbul")).date()
    try:
        universe = load_bist100_universe(as_of)
    except (OSError, ValueError) as exc:
        logger.warning("BIST100 snapshot unavailable or outside effective period")
        raise HTTPException(status_code=404, detail="Current BIST100 roster unavailable") from exc
    return JSONResponse(
        content={
            "market": "tr",
            "index": "BIST100",
            "as_of": as_of.isoformat(),
            "effective_from": universe.effective_from.isoformat(),
            "effective_to": universe.effective_to.isoformat(),
            "verified_on": universe.verified_on.isoformat(),
            "source_urls": list(universe.source_urls),
            "symbols": list(universe.symbols),
            "target_symbols": 100,
            "note": "Dated index membership only, not a live Yahoo quote or broker permission.",
        },
        headers={"Cache-Control": "no-store, private", "X-Content-Type-Options": "nosniff"},
    )

@router.get(
    "/four-market/batch-progress",
    summary="Read an operator-approved four-market 400-stock progress report",
    description=(
        "Admin-only, pre-generated local --status JSON. Never starts a Yahoo scan, "
        "enumerates server directories, accepts filenames over HTTP, reads SQLite "
        "or places brokerage orders."
    ),
)
def get_four_market_batch_progress(request: Request):
    """Fail closed if admin auth or the operator-configured JSON is absent."""
    if not is_auth_enabled():
        raise HTTPException(status_code=404, detail="Four-market progress unavailable")
    session = request.cookies.get(COOKIE_NAME)
    if not session or not verify_session(session):
        raise HTTPException(status_code=401, detail="Admin login required")
    try:
        report = load_configured_four_market_batch_progress()
    except FourMarketProgressUnavailable as exc:
        raise HTTPException(status_code=404, detail="Four-market progress not configured") from exc
    except FourMarketProgressInvalid as exc:
        logger.warning("Configured four-market progress JSON failed validation")
        raise HTTPException(status_code=422, detail="Four-market progress failed validation") from exc
    return JSONResponse(
        content=report,
        headers={"Cache-Control": "no-store, private", "X-Content-Type-Options": "nosniff"},
    )
