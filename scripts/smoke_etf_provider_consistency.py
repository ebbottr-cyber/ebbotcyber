"""Compare actual two isolated forward-adjusted ETF history providers.

Research-only smoke; the two sources are requested for the same symbol,
same as-of market session and history range in one run. Source outages are
BLOCKED, price disagreements are REVIEW, and only alignment within the
stated thresholds is CONSISTENT. No broker, orders or strategy promotion.
"""
from __future__ import annotations

from datetime import date
import json
import sys

from src.core.provider_consistency import compare_adjusted_close_sources
from src.core.etf_rotation import RotationParams
from src.core.rotation_timing_adapter import evaluate_single_asset_rotation_history
from src.core.trading_calendar import get_effective_trading_date
from src.services.etf_rotation_service import data_quality_warnings, load_closes


def main() -> int:
    from data_provider.base import DataFetcherManager
    from data_provider.baostock_fetcher import BaostockFetcher
    from data_provider.efinance_fetcher import EfinanceFetcher

    symbol = "510300"
    end = get_effective_trading_date("cn")
    sources = {
        "EfinanceFetcher": EfinanceFetcher(),
        "BaostockFetcher": BaostockFetcher(),
    }
    validated = {}
    try:
        for label, fetcher in sources.items():
            # Explicitly single-provider manager: never mistake fallback data
            # from another vendor for the provider being tested.
            mgr = DataFetcherManager(fetchers=[fetcher])
            loaded = load_closes(mgr, [symbol], years=2, end=end)
            if symbol in loaded.failed:
                raise RuntimeError(f"{label} unavailable: {loaded.failed[symbol][:170]}")
            if symbol not in loaded.closes.columns or loaded.sources.get(symbol) != label:
                raise RuntimeError(f"{label} did not supply an adjusted series")
            warnings = data_quality_warnings(loaded)
            if warnings:
                raise RuntimeError(f"{label} history quality warning: {warnings[0][:150]}")
            validated[label] = loaded.closes[symbol].copy()

        report = compare_adjusted_close_sources(
            validated["EfinanceFetcher"], validated["BaostockFetcher"],
            asset_code=symbol, left_source="EfinanceFetcher",
            right_source="BaostockFetcher", min_aligned_sessions=200,
            min_coverage_pct=99.0,
            p95_daily_gap_limit_bps=15.0,
            max_daily_gap_limit_bps=150.0,
            total_return_gap_limit_pp=1.0,
        )
        # Strategy comparisons must use *exactly identical* trading dates;
        # even a missing early observation changes possible signal timing.
        if not validated["EfinanceFetcher"].index.equals(validated["BaostockFetcher"].index):
            raise ValueError("provider session calendars differ; cannot compare strategy outcomes")
        results = {}
        # Quantify *strategy* result sensitivity to each provider separately:
        # same parameters and seed; reported outcomes are not investment claims.
        params = RotationParams(lookback_days=40, rebalance="weekly",
                                top_n=1, switch_buffer_pct=2.0, cost_bps=10.0)
        for source, series in validated.items():
            outcome = evaluate_single_asset_rotation_history(
                series.to_frame(symbol), asset_code=symbol, params=params,
                simulations=100, seed=42,
            )
            results[source] = {
                "entries": outcome.entry_count,
                "observed_net_return_pct": outcome.observed_return_pct,
                "max_drawdown_pct": outcome.observed_max_drawdown_pct,
            }
        ret_gap = abs(results["EfinanceFetcher"]["observed_net_return_pct"] -
                      results["BaostockFetcher"]["observed_net_return_pct"])
        payload = {
            "status": report.status,
            "symbol": symbol,
            "as_of": end.isoformat() if isinstance(end, date) else str(end),
            "alignment": report.to_dict(),
            "strategy_by_provider": results,
            "strategy_return_gap_pp": ret_gap,
            "research_only": True,
        }
        print(json.dumps(payload, ensure_ascii=False, allow_nan=False))
        return 0 if report.status == "CONSISTENT" else 1
    except Exception as exc:
        print(json.dumps({
            "status": "BLOCKED",
            "symbol": symbol,
            "type": type(exc).__name__,
            "message": str(exc)[:300],
            "research_only": True,
        }, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
