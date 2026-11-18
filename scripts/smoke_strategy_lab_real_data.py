"""Read-only live-provider smoke for Strategy Success Lab (no trading).

Uses existing adjusted ETF historical price providers and exchange calendars.
Reports success only when actual external price data passes the strict
production research service and yields an informative timing benchmark.
"""
from __future__ import annotations

import json
import math
import os
import sys
from datetime import date
from types import SimpleNamespace

from src.services.strategy_lab_service import analyze_configured_etf


def main() -> int:
    # This is a disposable benchmark sample, not a recommendation or an
    # addition to the user's tradable markets. No broker login or secrets.
    asset = "510300"
    config = SimpleNamespace(
        etf_rotation_pool=[asset],
        etf_rotation_backtest_years=2,
        etf_rotation_lookback_days=40,
        etf_rotation_rebalance="weekly",
        etf_rotation_switch_buffer_pct=2.0,
        etf_rotation_cost_bps=10.0,
    )
    try:
        report = analyze_configured_etf(
            asset_code=asset,
            simulations=100,
            config=config,
        )
        r = report["result"]
        assert report["research_only"] is True
        assert report["data_source"] not in ("", "unknown")
        assert r["entry_count"] >= 1
        assert r["distinct_random_schedules"] >= 2 and r["informative"]
        assert r["total_bars"] >= 60
        assert 0.0 <= r["fraction_random_at_least_observed"] <= 1.0
        for key in ("observed_return_pct", "observed_max_drawdown_pct",
                    "random_median_return_pct", "buy_and_hold_return_pct"):
            assert math.isfinite(r[key]), key
        # Safely print only data source metadata and statistical outputs.
        print(json.dumps({
            "status": "PASS",
            "asset": asset,
            "provider": report["data_source"],
            "history_start": report["history_start"],
            "history_end": report["history_end"],
            "entries": r["entry_count"],
            "observed_return_pct": r["observed_return_pct"],
            "random_median_return_pct": r["random_median_return_pct"],
            "random_fraction_at_least_observed": r["fraction_random_at_least_observed"],
            "samples": r["simulations"],
            "research_only": True,
        }, ensure_ascii=False, allow_nan=False))
        return 0
    except Exception as exc:
        # A provider outage, calendar issue or unsuitable history is not a pass.
        print(json.dumps({
            "status": "BLOCKED",
            "type": type(exc).__name__,
            "message": str(exc)[:240],
            "research_only": True,
        }, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
