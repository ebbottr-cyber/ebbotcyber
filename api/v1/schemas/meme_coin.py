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
