# -*- coding: utf-8 -*-
"""Data capability and quality endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from api.deps import get_config_dep
from api.v1.schemas.common import ErrorResponse
from api.v1.schemas.data_capability import DataCapabilityOverviewResponse
from api.v1.schemas.tr_market_overview import TurkishMarketOverviewResponse
from src.config import Config
from src.services.data_capability_service import DataCapabilityService
from src.services.tr_market_overview_service import get_overview as get_tr_market_overview
from src.auth import is_auth_enabled

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
    "/equity-coverage",
    summary="Read operator-provided four-market equity coverage evidence",
    description="Metadata-only review of a configured local report; no price fetch, symbol lists or orders.",
)
def get_equity_coverage(response: Response) -> dict:
    """Read a fixed operator-selected file; clients cannot supply a path."""
    from src.services.equity_data_coverage_reader import (
        read_equity_coverage_report,
        unavailable_equity_coverage_report,
    )

    response.headers["Cache-Control"] = "no-store"
    # The global /api/v1/* middleware only requires a session when admin auth
    # is configured. Never expose an operator's local coverage report through
    # the otherwise public API when this protection has been disabled.
    if not is_auth_enabled():
        return unavailable_equity_coverage_report("administrator_auth_required")
    return read_equity_coverage_report()


@router.get(
    "/bist-identity",
    summary="Read private BIST KAP/XIST reconciliation aggregate only",
    description="Read-only operator report; never includes symbols, ISINs, prices, or paths.",
)
def get_bist_identity_summary(response: Response) -> dict:
    """Apply the existing admin session gate and prevent auth-off disclosure."""
    from src.services.bist_identity_report_reader import (
        read_bist_identity_summary,
        unavailable_bist_identity_report,
    )

    response.headers["Cache-Control"] = "no-store"
    if not is_auth_enabled():
        return unavailable_bist_identity_report("administrator_auth_required")
    return read_bist_identity_summary()


@router.get(
    "/tr-market-overview",
    response_model=TurkishMarketOverviewResponse,
    summary="Delayed Turkish market overview",
    description=(
        "Read-only, best-effort Yahoo daily prices for BIST 100, BIST 30 and TRY FX pairs. "
        "Never executable/live quotes; unavailable and stale data produce null prices."
    ),
)
def get_turkish_market_overview() -> TurkishMarketOverviewResponse:
    return TurkishMarketOverviewResponse.model_validate(get_tr_market_overview())
