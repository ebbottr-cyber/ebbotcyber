"""Read-only Solana meme-coin strategy inventory.

There are intentionally no order, wallet, or strategy-enable endpoints.
"""
from fastapi import APIRouter, Security
from fastapi.security import APIKeyCookie

from api.v1.schemas.meme_coin import MemeCoinOverview
from src.auth import COOKIE_NAME
from src.services.meme_coin_strategy_service import get_meme_coin_overview

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
