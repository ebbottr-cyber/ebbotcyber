"""Read-only API response schema for the isolated meme-coin panel."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


class MemeCoinMetrics(BaseModel):
    trades: Optional[int] = None
    net_pnl_usd: Optional[float] = None
    win_rate_pct: Optional[float] = None


class RobinhoodAgentModule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: Literal["dex_scout", "liquidity_scout", "risk_sentinel", "sentiment_scout"]
    name: str
    status: Literal["not_connected"]


class MemeCoinStrategy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: Literal["new_launch", "momentum", "robinhood_chain"]
    name: str
    market: Literal["solana", "robinhood_chain"]
    data_sources: list[str]
    status: Literal["not_connected"]
    engine_connected: bool
    paper_trading_enabled: bool
    live_trading_enabled: bool
    risk_checks: list[str]
    agent_modules: list[RobinhoodAgentModule] = []
    metrics: MemeCoinMetrics


class MemeCoinOverview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    market: Literal["multi_chain"]
    mode: Literal["paper_planned"]
    live_trading_enabled: bool
    shared_risk_engine_connected: bool
    last_market_event_at: Optional[str] = None
    strategies: list[MemeCoinStrategy]


class MemeCoinCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy: Literal["new_launch", "momentum"]
    symbol: str
    token_address: str
    pool_address: str
    liquidity_usd: float
    volume_5m_usd: float
    change_5m_pct: float
    age_minutes: float
    buys_5m: int
    sells_5m: int
    research_score: float
    risk_status: Literal["unverified"]
    tradable: Literal[False]
    source: Literal["geckoterminal"]


class MemeCoinDiscoveryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy: Literal["new_launch", "momentum"]
    status: Literal["disabled", "ok", "unavailable"]
    source: Literal["geckoterminal"]
    observed_at: Optional[str] = None
    candidates: list[MemeCoinCandidate]
    error: Optional[str] = None


class RobinhoodRpcStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    network: Literal["testnet", "mainnet", "unknown"]
    chain_id_expected: Optional[int] = None
    chain_id_seen: Optional[int] = None
    block_number: Optional[int] = None
    status: Literal["disabled", "ok", "unavailable", "mismatch"]
    checked_at: Optional[str] = None
    error: Optional[str] = None
    trading_enabled: Literal[False]


class SolanaMintReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mint: str
    network: Literal["solana-mainnet"]
    status: Literal["disabled", "screened", "unavailable", "unsupported"]
    verdict: Literal["blocked", "review_only", "unknown"]
    slot: Optional[int] = None
    checked_at: Optional[str] = None
    token_program: Optional[str] = None
    mint_authority_revoked: Optional[bool] = None
    freeze_authority_revoked: Optional[bool] = None
    decimals: Optional[int] = None
    supply_base_units: Optional[str] = None
    blocking_reasons: list[str]
    remaining_unverified: list[str]
    full_safety_verified: Literal[False]
    tradable: Literal[False]


class SolanaImpactEstimate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: Literal["hypothetical_cpmm_50_50"]
    liquidity_usd: float
    order_usd: float
    fee_bps: int
    adverse_slippage_bps: int
    modeled_fee_usd: float
    modeled_output_value_usd: float
    modeled_min_output_value_usd: float
    modeled_price_impact_pct: float
    modeled_total_cost_pct: float
    order_vs_liquidity_pct: float
    flags: list[str]
    paper_review_status: Literal["blocked", "research_only"]
    real_quote_available: Literal[False]
    tradable: Literal[False]


class SolanaConcentrationReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mint: str
    network: Literal["solana-mainnet"]
    status: Literal["disabled", "screened", "unavailable"]
    verdict: Literal["unknown", "review_only", "concentration_signal"]
    checked_at: Optional[str] = None
    supply_slot: Optional[int] = None
    accounts_slot: Optional[int] = None
    supply_base_units: Optional[str] = None
    observed_accounts: int
    top_account_pct: Optional[float] = None
    top_ten_accounts_pct: Optional[float] = None
    observed_top_twenty_pct: Optional[float] = None
    warning_flags: list[str]
    interpretation: Literal["token_accounts_not_wallets"]
    owner_identity_verified: Literal[False]
    pool_vaults_classified: Literal[False]
    full_safety_verified: Literal[False]
    tradable: Literal[False]


class SolanaPoolReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mint: str
    pool: str
    network: Literal["solana"]
    status: Literal["disabled", "screened", "unavailable"]
    verdict: Literal["unknown", "blocked", "review_only"]
    checked_at: Optional[str] = None
    geckoterminal_usd: Optional[float] = None
    dexscreener_usd: Optional[float] = None
    difference_pct: Optional[float] = None
    dex_id: Optional[str] = None
    onchain_account_found: Optional[bool] = None
    onchain_owner_program: Optional[str] = None
    onchain_slot: Optional[int] = None
    flags: list[str]
    onchain_reserves_verified: Literal[False]
    liquidity_lock_verified: Literal[False]
    lp_owner_verified: Literal[False]
    pool_authenticity_verified: Literal[False]
    sellability_verified: Literal[False]
    tradable: Literal[False]


class ObservedTokenAccountOwnerGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner_address: str
    sampled_token_accounts: int
    share_of_total_supply_pct: float


class SolanaOwnerGroupReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mint: str
    network: Literal["solana-mainnet"]
    status: Literal["disabled", "screened", "unavailable"]
    verdict: Literal["unknown", "review_only", "concentration_signal"]
    checked_at: Optional[str] = None
    observed_top_token_accounts: int
    observed_owner_groups: int
    largest_observed_owner_share_pct: Optional[float] = None
    owner_groups: list[ObservedTokenAccountOwnerGroup]
    flags: list[str]
    interpretation: Literal["observed_token_account_owner_not_beneficial_owner"]
    vault_classification_verified: Literal[False]
    beneficial_ownership_verified: Literal[False]
    full_safety_verified: Literal[False]
    tradable: Literal[False]
