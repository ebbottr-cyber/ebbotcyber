"""Read-only Solana meme-coin strategy inventory.

There are intentionally no order, wallet, or strategy-enable endpoints.
"""
from typing import Literal

from fastapi import APIRouter, Query, Security
from fastapi.security import APIKeyCookie

from api.v1.schemas.meme_coin import MemeCoinOverview, MemeCoinDiscoveryResponse, RobinhoodRpcStatus
from src.auth import COOKIE_NAME
from src.services.meme_coin_strategy_service import get_meme_coin_overview
from src.services.meme_coin_discovery import scan_strategy
from src.services.meme_coin_robinhood import get_robinhood_rpc_status

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
