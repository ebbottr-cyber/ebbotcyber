"""Independent multi-chain meme-coin strategy registry (read-only bootstrap).

This module deliberately does not import stock signal engines, custodial wallet
code, live order routers, or third-party APIs. Live trading is not implemented.
"""
from __future__ import annotations

from copy import deepcopy

_STRATEGIES = (
    {
        "id": "new_launch",
        "name": "New Launch",
        "market": "solana",
        "data_sources": ["Pump.fun", "Solana pool events"],
        "status": "not_connected",
        "engine_connected": False,
        "paper_trading_enabled": False,
        "live_trading_enabled": False,
        "risk_checks": [
            "token_authorities",
            "holder_concentration",
            "liquidity",
            "sell_simulation",
        ],
        "metrics": {
            "trades": None,
            "net_pnl_usd": None,
            "win_rate_pct": None,
        },
    },
    {
        "id": "momentum",
        "name": "Momentum",
        "market": "solana",
        "data_sources": ["GMGN", "Solana DEX market data"],
        "status": "not_connected",
        "engine_connected": False,
        "paper_trading_enabled": False,
        "live_trading_enabled": False,
        "risk_checks": [
            "volume_quality",
            "liquidity",
            "wallet_concentration",
            "price_impact",
        ],
        "metrics": {
            "trades": None,
            "net_pnl_usd": None,
            "win_rate_pct": None,
        },
    },
    {
        "id": "robinhood_chain",
        "name": "Robinhood Chain Agent Research",
        "market": "robinhood_chain",
        "data_sources": [
            "Robinhood Chain RPC (optional health check)",
            "EVM DEX discovery (planned)",
            "OpenCatz AI integration (planned)",
        ],
        "status": "not_connected",
        "engine_connected": False,
        "paper_trading_enabled": False,
        "live_trading_enabled": False,
        "risk_checks": [
            "evm_contract_permissions",
            "pool_liquidity",
            "wallet_concentration",
            "sell_simulation",
        ],
        "metrics": {
            "trades": None,
            "net_pnl_usd": None,
            "win_rate_pct": None,
        },
    },
)


def get_meme_coin_overview() -> dict:
    """Return a disconnected, fail-closed strategy inventory.

    Paper trading is the intended future execution mode, not a claim that a
    simulation has already run. Explicit None metrics mean unavailable data.
    """
    return {
        "market": "multi_chain",
        "mode": "paper_planned",
        "live_trading_enabled": False,
        "shared_risk_engine_connected": False,
        "last_market_event_at": None,
        "strategies": deepcopy(_STRATEGIES),
    }
