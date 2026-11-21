"""Ledger adapter tests independent of any database or market provider."""
from dataclasses import dataclass
from datetime import date, timedelta
import unittest

from src.core.rotation_timing_adapter import evaluate_rotation_trade_timing
from src.core.random_benchmark import evaluate_random_benchmark


@dataclass(frozen=True)
class RotationTrade:
    exec_date: date
    from_weights: dict
    to_weights: dict


def _input():
    dates = [date(2026, 1, 1) + timedelta(days=i) for i in range(9)]
    prices = [100, 101, 102, 99, 97, 101, 103, 102, 105]
    trades = [
        RotationTrade(dates[1], {"CASH": 1.0}, {"AAA": 1.0}),
        RotationTrade(dates[3], {"AAA": 1.0}, {"CASH": 1.0}),
        RotationTrade(dates[5], {"CASH": 1.0}, {"AAA": 1.0}),
        RotationTrade(dates[7], {"AAA": 1.0}, {"CASH": 1.0}),
    ]
    return dates, prices, trades


class RotationTimingAdapterTests(unittest.TestCase):
    def test_matches_precomputed_exposure_and_costs(self):
        dates, prices, trades = _input()
        result = evaluate_rotation_trade_timing(dates, prices, trades, asset_code="AAA", simulations=400,
                                                fee_bps=10, slippage_bps=4, seed=3)
        expected = evaluate_random_benchmark(prices, [0, 1, 1, 0, 0, 1, 1, 0],
                                             simulations=400, fee_bps=10, slippage_bps=4, seed=3)
        self.assertEqual(result, expected)
        self.assertEqual(result.entry_count, 2)
        self.assertEqual(result.exposure_bars, 4)

    def test_final_open_position_liquidated_only_once(self):
        dates, prices, trades = _input()
        result = evaluate_rotation_trade_timing(dates, prices, trades[:3], asset_code="AAA", simulations=100,
                                                fee_bps=10)
        self.assertEqual(result.entry_count, 2)
        self.assertEqual(result.exposure_bars, 5)
        expected = evaluate_random_benchmark(prices, [0, 1, 1, 0, 0, 1, 1, 1],
                                             simulations=100, fee_bps=10)
        self.assertEqual(result, expected)

    def test_rejects_missing_trade_and_out_of_order(self):
        dates, prices, trades = _input()
        for bad_trades in ([trades[1]], [trades[1], trades[0]], [trades[0], trades[0]]):
            with self.subTest(trades=bad_trades), self.assertRaises(ValueError):
                evaluate_rotation_trade_timing(dates, prices, bad_trades, asset_code="AAA", simulations=10)

    def test_rejects_multi_asset_safe_asset_and_partial_exposure(self):
        dates, prices, trades = _input()
        examples = [
            {"BBB": 1.0},
            {"AAA": 0.5, "CASH": 0.5},
            {"AAA": 0.7, "CASH": 0.2},
        ]
        for target in examples:
            with self.subTest(target=target), self.assertRaises(ValueError):
                evaluate_rotation_trade_timing(dates, prices,
                    [RotationTrade(dates[1], {"CASH": 1.0}, target)], asset_code="AAA", simulations=10)

    def test_rejects_entry_on_final_close(self):
        dates, prices, trades = _input()
        last = RotationTrade(dates[-1], {"CASH": 1.0}, {"AAA": 1.0})
        with self.assertRaises(ValueError):
            evaluate_rotation_trade_timing(dates, prices, trades + [last], asset_code="AAA", simulations=10)

    def test_final_close_exit_uses_same_forced_exit_cost(self):
        dates, prices, trades = _input()
        ending = RotationTrade(dates[-1], {"AAA": 1.0}, {"CASH": 1.0})
        expected = evaluate_rotation_trade_timing(dates, prices, trades[:3], asset_code="AAA", simulations=100)
        observed = evaluate_rotation_trade_timing(dates, prices, trades[:3] + [ending],
                                                  asset_code="AAA", simulations=100)
        self.assertEqual(observed, expected)

    def test_rejects_wrong_window_dates(self):
        dates, prices, trades = _input()
        examples = [dates[:-1] + [dates[-2]], dates[1:] + [dates[-1]]]
        for invalid_dates in examples:
            with self.assertRaises(ValueError):
                evaluate_rotation_trade_timing(invalid_dates, prices, trades, asset_code="AAA", simulations=10)

    def test_rejects_all_cash_or_no_trades(self):
        dates, prices, _ = _input()
        with self.assertRaises(ValueError):
            evaluate_rotation_trade_timing(dates, prices, [], asset_code="AAA", simulations=10)


def test_actual_etf_rotation_single_asset_history():
    """Runs the real strategy core, not a mocked schedule or guessed signal."""
    import numpy as np
    import pandas as pd
    from src.core.etf_rotation import RotationParams
    from src.core.rotation_timing_adapter import evaluate_single_asset_rotation_history

    dates = pd.bdate_range("2025-01-01", periods=90)
    prices = 100 * np.cumprod(np.full(len(dates), 1.003))
    frame = pd.DataFrame({"AAA": prices}, index=dates)
    report = evaluate_single_asset_rotation_history(
        frame, asset_code="AAA", params=RotationParams(lookback_days=10, rebalance="weekly", cost_bps=9),
        simulations=100, slippage_bps=2, seed=123,
    )
    assert report.entry_count == 1
    assert report.exposure_bars > 0
    assert report.total_bars < len(frame) - 10
    assert report.observed_return_pct > 0
    assert report.simulations == 100


def test_actual_etf_rotation_rejects_bad_input_and_cash_only():
    import numpy as np
    import pandas as pd
    import pytest
    from src.core.etf_rotation import RotationParams
    from src.core.rotation_timing_adapter import evaluate_single_asset_rotation_history

    idx = pd.bdate_range("2025-01-01", periods=90)
    falling = pd.DataFrame({"AAA": 100 * np.cumprod(np.full(len(idx), 0.997))}, index=idx)
    params = RotationParams(lookback_days=10, rebalance="weekly")
    with pytest.raises(ValueError, match="long position"):
        evaluate_single_asset_rotation_history(falling, asset_code="AAA", params=params, simulations=10)
    with pytest.raises(ValueError, match="top_n=1"):
        evaluate_single_asset_rotation_history(falling, asset_code="AAA", params=RotationParams(top_n=2), simulations=10)
    bad = falling.copy()
    bad.iloc[15, 0] = np.nan
    with pytest.raises(ValueError, match="finite and positive"):
        evaluate_single_asset_rotation_history(bad, asset_code="AAA", params=params, simulations=10)


if __name__ == "__main__":
    unittest.main()
