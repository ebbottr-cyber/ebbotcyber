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


class SolanaOrcaVaultReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mint: str
    pool: str
    network: Literal["solana-mainnet"]
    protocol: Literal["orca_whirlpool"]
    status: Literal["disabled", "unsupported", "unavailable", "screened"]
    verdict: Literal["unknown", "blocked", "review_only"]
    checked_at: Optional[str] = None
    pool_slot: Optional[int] = None
    vault_slot: Optional[int] = None
    pool_program: Optional[str] = None
    mint_a: Optional[str] = None
    mint_b: Optional[str] = None
    vault_a: Optional[str] = None
    vault_b: Optional[str] = None
    vault_a_raw_amount: Optional[str] = None
    vault_b_raw_amount: Optional[str] = None
    vault_a_decimals: Optional[int] = None
    vault_b_decimals: Optional[int] = None
    clmm_liquidity_raw: Optional[str] = None
    vault_authority_matches_pool: bool
    warnings: list[str]
    vault_reserves_observed: bool
    active_swap_depth_verified: Literal[False]
    liquidity_lock_verified: Literal[False]
    lp_withdrawal_authority_verified: Literal[False]
    sellability_verified: Literal[False]
    tradable: Literal[False]


class MemeCoinPaperLedgerStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy: Literal["new_launch", "momentum"]
    state: Literal["not_running"]
    realized_pnl_usd: Optional[float] = None


class MemeCoinPaperReplayStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["offline_replay_available"]
    data_source: Literal["operator_supplied_offline_fixture"]
    live_quotes_connected: Literal[False]
    paper_automated: Literal[False]
    live_trading_enabled: Literal[False]
    strategy_ledgers: list[MemeCoinPaperLedgerStatus]


class SolanaJupiterQuoteCapture(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capture_id: str
    source: Literal["jupiter_swap_v2_order_quote_only"]
    strategy: Literal["new_launch", "momentum"]
    mint: str
    side: Literal["buy", "sell"]
    input_mint: str
    output_mint: str
    amount_in_raw: str
    amount_out_raw: str
    fee_bps: int
    router: str
    captured_at_ms: int
    captured_at: str
    transaction_returned: Literal[False]
    execution_is_real: Literal[False]
    token_safety_verified: Literal[False]
    estimated_network_fee_available: Literal[False]
    tradable: Literal[False]


class SolanaJupiterQuotePreview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy: Literal["new_launch", "momentum"]
    mint: str
    side: Literal["buy", "sell"]
    source: Literal["jupiter_swap_v2_order_quote_only"]
    input_mint: str
    output_mint: str
    amount_in_raw: str
    status: Literal["disabled", "ok", "unavailable", "rate_limited"]
    quote: Optional[SolanaJupiterQuoteCapture] = None
    error: Optional[str] = None
    live_quote_preview: bool
    wallet_connected: Literal[False]
    transaction_requested: Literal[False]
    transaction_submitted: Literal[False]
    tradable: Literal[False]


class MemeCoinOfflineGuardLedger(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy: Literal["new_launch", "momentum"]
    mode: Literal["offline_only"]
    live_orders_enabled: Literal[False]


class MemeCoinOfflineRiskReadiness(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["offline_safeguards_available"]
    archive_mode: Literal["manual_local_sqlite_only"]
    journal_online: Literal[False]
    paper_engine_running: Literal[False]
    live_trading_enabled: Literal[False]
    risk_facts_verified_from_market: Literal[False]
    strategy_ledgers: list[MemeCoinOfflineGuardLedger]


class MemeCoinMtmStrategyReadiness(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy: Literal["new_launch", "momentum"]
    status: Literal["not_running"]


class MemeCoinMtmReadiness(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["offline_mtm_recovery_available"]
    mark_source: Literal["unverified_offline_assumptions"]
    database_online: Literal[False]
    paper_scheduler_running: Literal[False]
    live_trading_enabled: Literal[False]
    strategies: list[MemeCoinMtmStrategyReadiness]
