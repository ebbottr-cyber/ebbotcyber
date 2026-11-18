"""Real adjusted ETF price validation through sequential OOS folds and holdout.

This is a read-only historical smoke, not a trading evaluation or an
automatically tuned strategy. Provider outages or noninformative holdout
windows are reported as NOT_EVALUABLE rather than passing silently.
"""
from __future__ import annotations

from dataclasses import asdict
import json
import math
import sys

from src.core.etf_rotation import RotationParams
from src.core.temporal_validation import evaluate_temporal_holdout
from src.core.trading_calendar import get_effective_trading_date
from src.services.etf_rotation_service import data_quality_warnings, load_closes


def main() -> int:
    from data_provider.base import DataFetcherManager

    symbol = "510300"
    try:
        end = get_effective_trading_date("cn")
        loaded = load_closes(DataFetcherManager(), [symbol], years=2, end=end)
        if symbol not in loaded.closes.columns or symbol in loaded.failed:
            raise ValueError("real forward-adjusted ETF history unavailable")
        warnings = data_quality_warnings(loaded)
        if warnings:
            raise ValueError(f"historical price quality failed: {warnings[0][:120]}")

        report = evaluate_temporal_holdout(
            loaded.closes[[symbol]],
            asset_code=symbol,
            params=RotationParams(
                lookback_days=40,
                rebalance="weekly",
                top_n=1,
                switch_buffer_pct=2.0,
                cost_bps=10.0,
            ),
            min_training_intervals=180,
            walk_forward_folds=3,
            min_fold_intervals=30,
            holdout_fraction=0.2,
            simulations=500,
            slippage_bps=0,
            seed=42,
        )
        summary = []
        for window in report.windows:
            bench = window.benchmark
            summary.append({
                "label": window.label,
                "kind": window.kind,
                "status": window.status,
                "training_end": window.training_end,
                "test_start_close": window.test_start_close,
                "test_end_close": window.test_end_close,
                "test_intervals": window.test_intervals,
                "entries": bench.entry_count if bench else 0,
                "observed_return_pct": bench.observed_return_pct if bench else None,
                "random_median_return_pct": bench.random_median_return_pct if bench else None,
                "fraction_random_at_least_observed": bench.fraction_random_at_least_observed if bench else None,
                "informative": bench.informative if bench else False,
            })
        # Repeated folds with no long exposure have no random timing
        # comparison. This is useful output, but not a successful OOS test.
        sufficient = report.holdout_status == "EVALUATED" and report.evaluated_folds >= 2
        print(json.dumps({
            "status": "PASS" if sufficient else "NOT_EVALUABLE",
            "asset_code": symbol,
            "provider": loaded.sources.get(symbol, "unknown"),
            "method": report.mode,
            "parameters_fixed": True,
            "folds_evaluated": report.evaluated_folds,
            "holdout_status": report.holdout_status,
            "windows": summary,
            "research_only": True,
        }, ensure_ascii=False, allow_nan=False))
        return 0 if sufficient else 1
    except Exception as exc:
        print(json.dumps({
            "status": "BLOCKED",
            "type": type(exc).__name__,
            "message": str(exc)[:240],
            "research_only": True,
        }, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
