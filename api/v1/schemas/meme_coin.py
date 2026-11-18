"""Read-only API response schema for the isolated meme-coin panel."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


class MemeCoinMetrics(BaseModel):
    trades: Optional[int] = None
    net_pnl_usd: Optional[float] = None
    win_rate_pct: Optional[float] = None


class MemeCoinStrategy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: Literal["new_launch", "momentum"]
    name: str
    market: Literal["solana"]
    data_sources: list[str]
    status: Literal["not_connected"]
    engine_connected: bool
    paper_trading_enabled: bool
    live_trading_enabled: bool
    risk_checks: list[str]
    metrics: MemeCoinMetrics


class MemeCoinOverview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    market: Literal["solana"]
    mode: Literal["paper_planned"]
    live_trading_enabled: bool
    shared_risk_engine_connected: bool
    last_market_event_at: Optional[str] = None
    strategies: list[MemeCoinStrategy]
