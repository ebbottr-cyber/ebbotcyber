"""Opt-in, read-only research service for one configured ETF vs cash.

Never changes runtime strategy weights, decisions, orders, or portfolio data.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import date
import re
from typing import Any, Optional

from src.core.etf_rotation import RotationParams
from src.core.rotation_timing_adapter import evaluate_single_asset_rotation_history
from src.services.etf_rotation_service import CALENDAR_MARKET, data_quality_warnings, load_closes


class BenchmarkDataUnavailable(RuntimeError):
    """A configured ETF lacks suitable validated historical prices."""


def eligible_etfs(config: Any) -> list[str]:
    """Only show six-digit ETF codes explicitly enabled in the rotation pool."""
    pool = getattr(config, "etf_rotation_pool", ()) or ()
    return sorted({c for item in pool if (c := str(item).strip()) and re.fullmatch(r"[0-9]{6}", c)})


def analyze_configured_etf(
    *,
    asset_code: str,
    simulations: int = 500,
    config: Any,
    fetcher_manager: Optional[Any] = None,
    end: Optional[date] = None,
) -> dict[str, Any]:
    """Compute an observation, without persisting or placing any trade.

    The market provider and trading calendar are the ones used by EBBot's
    existing ETF rotation service. A source without confirmed forward-adjusted
    closes or with data-quality warnings cannot supply a benchmark.
    """
    if asset_code not in eligible_etfs(config):
        raise ValueError("ETF is not in the configured rotation pool")
    if isinstance(simulations, bool) or not isinstance(simulations, int) or not 100 <= simulations <= 4000:
        raise ValueError("simulations must be between 100 and 4000")

    if fetcher_manager is None:
        from data_provider import DataFetcherManager

        fetcher_manager = DataFetcherManager()
    if end is None:
        from src.core.trading_calendar import get_effective_trading_date

        end = get_effective_trading_date(CALENDAR_MARKET)

    years = max(1, min(5, int(config.etf_rotation_backtest_years)))
    loaded = load_closes(fetcher_manager, [asset_code], years, end=end)
    if asset_code in loaded.failed or asset_code not in loaded.closes.columns:
        raise BenchmarkDataUnavailable("Adjusted historical ETF data is unavailable")
    warnings = data_quality_warnings(loaded)
    if warnings:
        raise BenchmarkDataUnavailable("ETF history did not pass data-quality checks")

    try:
        result = evaluate_single_asset_rotation_history(
            loaded.closes[[asset_code]],
            asset_code=asset_code,
            params=RotationParams(
                lookback_days=int(config.etf_rotation_lookback_days),
                rebalance=config.etf_rotation_rebalance,
                top_n=1,
                switch_buffer_pct=float(config.etf_rotation_switch_buffer_pct),
                cost_bps=float(config.etf_rotation_cost_bps),
            ),
            simulations=simulations,
            slippage_bps=0.0,
            seed=42,
        )
    except ValueError as exc:
        # Incomplete history or an all-cash strategy is not a usable benchmark.
        raise BenchmarkDataUnavailable("Not enough eligible historical ETF trades for comparison") from exc

    dates = loaded.closes.index
    return {
        "asset_code": asset_code,
        "strategy": "single_etf_vs_cash",
        "research_only": True,
        "data_source": loaded.sources.get(asset_code, "unknown"),
        "history_start": dates[0].date().isoformat(),
        "history_end": dates[-1].date().isoformat(),
        "lookback_days": int(config.etf_rotation_lookback_days),
        "rebalance": config.etf_rotation_rebalance,
        "fee_bps": float(config.etf_rotation_cost_bps),
        "slippage_bps": 0.0,
        "result": asdict(result),
    }
