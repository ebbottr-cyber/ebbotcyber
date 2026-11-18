"""Read-only Solana meme-coin strategy inventory.

There are intentionally no order, wallet, or strategy-enable endpoints.
"""
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Security
from fastapi.security import APIKeyCookie

from api.v1.schemas.meme_coin import (MemeCoinOverview, MemeCoinDiscoveryResponse, RobinhoodRpcStatus, SolanaMintReview, SolanaImpactEstimate, SolanaConcentrationReview)
from src.auth import COOKIE_NAME
from src.services.meme_coin_strategy_service import get_meme_coin_overview
from src.services.meme_coin_discovery import scan_strategy
from src.services.meme_coin_robinhood import get_robinhood_rpc_status
from src.services.meme_coin_solana_risk import review_mint, estimate_cpmm_impact
from src.services.meme_coin_solana_holders import review_concentration

admin_session_cookie = APIKeyCookie(
    name=COOKIE_NAME, scheme_name="AdminSessionCookie", auto_error=False
)
router = APIRouter(dependencies=[Security(admin_session_cookie)])


@router.get(
    "/overview",
    response_model=MemeCoinOverview,
    operation_id="getMemeCoinOverview",
    summary="Read-only meme-coin strategy overview",
)
def get_overview() -> MemeCoinOverview:
    return MemeCoinOverview(**get_meme_coin_overview())


@router.get(
    "/candidates",
    response_model=MemeCoinDiscoveryResponse,
    operation_id="scanMemeCoinCandidates",
    summary="Opt-in, read-only Solana pool discovery by strategy",
)
def get_candidates(
    strategy: Literal["new_launch", "momentum"] = Query(...),
) -> MemeCoinDiscoveryResponse:
    # No trades, wallet functions, or simulated orders in this endpoint.
    return MemeCoinDiscoveryResponse(**scan_strategy(strategy))


@router.get(
    "/robinhood/status",
    response_model=RobinhoodRpcStatus,
    operation_id="getRobinhoodRpcStatus",
    summary="Read-only Robinhood Chain network health",
)
def robinhood_status() -> RobinhoodRpcStatus:
    return RobinhoodRpcStatus(**get_robinhood_rpc_status())


@router.get(
    "/solana/mint-review",
    response_model=SolanaMintReview,
    operation_id="getSolanaMintReview",
    summary="Opt-in, read-only classic Solana token mint authority snapshot",
)
def solana_mint_review(
    mint: str = Query(..., min_length=32, max_length=44),
) -> SolanaMintReview:
    try:
        return SolanaMintReview(**review_mint(mint))
    except ValueError:
        raise HTTPException(status_code=422, detail="invalid_mint_address")


@router.get(
    "/solana/impact",
    response_model=SolanaImpactEstimate,
    operation_id="estimateSolanaPoolImpact",
    summary="Hypothetical AMM impact for research only, never a live route quote",
)
def solana_impact(
    liquidity_usd: float = Query(..., ge=10000, le=1e10),
    order_usd: float = Query(25.0, ge=1, le=10000),
    fee_bps: int = Query(30, ge=0, le=200),
    adverse_slippage_bps: int = Query(100, ge=0, le=3000),
) -> SolanaImpactEstimate:
    try:
        return SolanaImpactEstimate(**estimate_cpmm_impact(
            liquidity_usd=liquidity_usd,
            order_usd=order_usd,
            fee_bps=fee_bps,
            adverse_slippage_bps=adverse_slippage_bps,
        ))
    except ValueError:
        raise HTTPException(status_code=422, detail="invalid_impact_parameters")


@router.get(
    "/solana/concentration",
    response_model=SolanaConcentrationReview,
    operation_id="getSolanaTokenAccountConcentration",
    summary="Read-only, opt-in top-token-account concentration signals",
)
def solana_concentration(
    mint: str = Query(..., min_length=32, max_length=44),
) -> SolanaConcentrationReview:
    try:
        return SolanaConcentrationReview(**review_concentration(mint))
    except ValueError:
        raise HTTPException(status_code=422, detail="invalid_mint_address")
