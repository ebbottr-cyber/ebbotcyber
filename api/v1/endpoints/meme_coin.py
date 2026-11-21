"""Read-only Solana meme-coin strategy inventory.

There are intentionally no order, wallet, or strategy-enable endpoints.
"""
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Security
from fastapi.security import APIKeyCookie

from api.v1.schemas.meme_coin import (MemeCoinOverview, MemeCoinDiscoveryResponse, RobinhoodRpcStatus, SolanaMintReview, SolanaImpactEstimate, SolanaConcentrationReview, SolanaPoolReview, SolanaOwnerGroupReview, SolanaOrcaVaultReview, MemeCoinPaperReplayStatus, SolanaJupiterQuotePreview, MemeCoinOfflineRiskReadiness, MemeCoinMtmReadiness, SolanaDualSourceMarkPreview, MemeCoinExitGuardReadiness)
from src.auth import COOKIE_NAME
from src.services.meme_coin_strategy_service import get_meme_coin_overview
from src.services.meme_coin_discovery import scan_strategy
from src.services.meme_coin_robinhood import get_robinhood_rpc_status
from src.services.meme_coin_solana_risk import review_mint, estimate_cpmm_impact
from src.services.meme_coin_solana_holders import review_concentration
from src.services.meme_coin_solana_pool import review_pool
from src.services.meme_coin_solana_owner_groups import review_owner_groups
from src.services.meme_coin_solana_orca import review_orca_vaults
from src.services.meme_coin_paper_replay import status as get_paper_replay_status
from src.services.meme_coin_paper_guard import readiness as get_paper_guard_readiness
from src.services.meme_coin_paper_mtm import readiness as get_mtm_readiness
from src.services.meme_coin_jupiter_quotes import quote_preview
from src.services.meme_coin_price_crosscheck import preview_crosscheck
from src.services.meme_coin_exit_feed_guard import readiness as get_exit_guard_readiness

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


@router.get(
    "/solana/pool-review",
    response_model=SolanaPoolReview,
    operation_id="reviewSolanaPoolLiquidity",
    summary="Opt-in read-only cross-source Solana pool account and liquidity research",
)
def solana_pool_review(
    mint: str = Query(..., min_length=32, max_length=44),
    pool: str = Query(..., min_length=32, max_length=44),
) -> SolanaPoolReview:
    try:
        return SolanaPoolReview(**review_pool(mint, pool))
    except ValueError:
        raise HTTPException(status_code=422, detail="invalid_pool_or_mint")


@router.get(
    "/solana/owner-groups",
    response_model=SolanaOwnerGroupReview,
    operation_id="reviewSolanaTokenAccountOwnerGroups",
    summary="Opt-in read-only group analysis for up to 10 largest token accounts",
)
def solana_owner_groups(
    mint: str = Query(..., min_length=32, max_length=44),
) -> SolanaOwnerGroupReview:
    try:
        return SolanaOwnerGroupReview(**review_owner_groups(mint))
    except ValueError:
        raise HTTPException(status_code=422, detail="invalid_mint_address")


@router.get(
    "/solana/orca-vaults",
    response_model=SolanaOrcaVaultReview,
    operation_id="reviewSolanaOrcaVaultReserves",
    summary="Opt-in onchain Orca Whirlpool vault snapshot (read-only)",
)
def solana_orca_vaults(
    mint: str = Query(..., min_length=32, max_length=44),
    pool: str = Query(..., min_length=32, max_length=44),
) -> SolanaOrcaVaultReview:
    try:
        return SolanaOrcaVaultReview(**review_orca_vaults(mint, pool))
    except ValueError:
        raise HTTPException(status_code=422, detail="invalid_mint_or_pool")


@router.get(
    "/paper/status",
    response_model=MemeCoinPaperReplayStatus,
    operation_id="getMemeCoinPaperReplayStatus",
    summary="Read-only status of offline paper replay capabilities (no live fills)",
)
def paper_replay_status() -> MemeCoinPaperReplayStatus:
    # Historical offline fixtures are never represented as live performance.
    # There are NO paper order-creation endpoints in the online service.
    return MemeCoinPaperReplayStatus(**get_paper_replay_status())


@router.get(
    "/solana/quote-preview",
    response_model=SolanaJupiterQuotePreview,
    operation_id="previewJupiterSwapV2QuoteOnly",
    summary="Opt-in Jupiter V2 no-taker quote preview; no order execution",
)
def solana_quote_preview(
    strategy: Literal["new_launch", "momentum"] = Query(...),
    mint: str = Query(..., min_length=32, max_length=44),
    side: Literal["buy", "sell"] = Query(...),
    amount_raw: int = Query(..., ge=1, le=10**15),
) -> SolanaJupiterQuotePreview:
    try:
        return SolanaJupiterQuotePreview(
            **quote_preview(strategy, mint, side, amount_raw)
        )
    except ValueError:
        raise HTTPException(status_code=422, detail="invalid_quote_preview_input")


@router.get(
    "/paper/risk-readiness",
    response_model=MemeCoinOfflineRiskReadiness,
    operation_id="getMemeCoinOfflineRiskReadiness",
    summary="Static read-only status of offline quote journal and paper risk safeguards",
)
def paper_risk_readiness() -> MemeCoinOfflineRiskReadiness:
    # No archive paths, captured quotes, DB writes or strategy orders.
    return MemeCoinOfflineRiskReadiness(**get_paper_guard_readiness())


@router.get(
    "/paper/mtm-readiness",
    response_model=MemeCoinMtmReadiness,
    operation_id="getMemeCoinOfflineMtmReadiness",
    summary="Read-only status of offline MTM and crash recovery (not running)",
)
def paper_mtm_readiness() -> MemeCoinMtmReadiness:
    # Never accesses local checkpoint files or enables a scheduler/order route.
    return MemeCoinMtmReadiness(**get_mtm_readiness())


@router.get(
    "/solana/mark-crosscheck",
    response_model=SolanaDualSourceMarkPreview,
    operation_id="getSolanaManualDualSourcePriceCrosscheck",
    summary="Opt-in manual Jupiter sell quote vs exact DEX pool price; no fills",
)
def solana_mark_crosscheck(
    strategy: Literal["new_launch", "momentum"] = Query(...),
    mint: str = Query(..., min_length=32, max_length=44),
    pool: str = Query(..., min_length=32, max_length=44),
    amount_raw: int = Query(..., ge=1, le=10**15),
) -> SolanaDualSourceMarkPreview:
    try:
        return SolanaDualSourceMarkPreview(
            **preview_crosscheck(strategy, mint, pool, amount_raw)
        )
    except ValueError:
        raise HTTPException(status_code=422, detail="invalid_mark_crosscheck_input")


@router.get(
    "/paper/exit-guard-readiness",
    response_model=MemeCoinExitGuardReadiness,
    operation_id="getMemeCoinExitGuardReadiness",
    summary="Static read-only status of V13 offline full-exit and feed guards",
)
def paper_exit_guard_readiness() -> MemeCoinExitGuardReadiness:
    # No file reads, side effects, real prices or order issuance.
    return MemeCoinExitGuardReadiness(**get_exit_guard_readiness())
