"""Deterministic tests of the isolated random timing benchmark."""

import math
import unittest

from src.core.random_benchmark import (
    _long_spells,
    _random_schedule,
    evaluate_random_benchmark,
)
import random


class RandomBenchmarkTests(unittest.TestCase):
    def test_reproducible_and_preserves_trade_structure(self):
        closes = [100, 101, 99, 100, 104, 103, 105, 102, 107, 106, 108]
        positions = [0, 1, 1, 0, 0, 1, 1, 1, 0, 0]
        a = evaluate_random_benchmark(closes, positions, simulations=500, fee_bps=10, slippage_bps=5, seed=7)
        b = evaluate_random_benchmark(closes, positions, simulations=500, fee_bps=10, slippage_bps=5, seed=7)
        self.assertEqual(a, b)
        self.assertEqual(a.entry_count, 2)
        self.assertEqual(a.exposure_bars, 5)
        self.assertEqual(a.total_bars, 10)
        self.assertTrue(a.informative)
        self.assertGreater(a.distinct_random_schedules, 1)
        self.assertGreaterEqual(a.fraction_random_at_least_observed, 0)
        self.assertLessEqual(a.fraction_random_at_least_observed, 1)
        rng = random.Random(5)
        for _ in range(500):
            candidate = _random_schedule(len(positions), [2, 3], rng)
            self.assertEqual(len(candidate), len(positions))
            self.assertEqual(_long_spells(candidate), [2, 3])
            self.assertEqual(sum(candidate), 5)

    def test_constant_market_charges_entries_and_exits(self):
        closes = [100] * 9
        positions = [0, 1, 1, 0, 1, 1, 0, 0]
        result = evaluate_random_benchmark(closes, positions, simulations=40, fee_bps=10, seed=11)
        expected = ((1 - 10 / 10000) ** 4 - 1) * 100
        self.assertAlmostEqual(result.observed_return_pct, expected)
        self.assertAlmostEqual(result.random_median_return_pct, expected)
        self.assertEqual(result.fraction_random_at_least_observed, 1.0)
        self.assertLess(result.observed_return_pct, 0)
        self.assertGreater(result.observed_max_drawdown_pct, 0)

    def test_all_long_is_noninformative(self):
        result = evaluate_random_benchmark([100, 101, 103, 110], [1, 1, 1], simulations=50, seed=10)
        self.assertFalse(result.informative)
        self.assertEqual(result.distinct_random_schedules, 1)
        self.assertEqual(result.observed_return_pct, result.random_median_return_pct)
        self.assertEqual(result.buy_and_hold_return_pct, result.observed_return_pct)

    def test_no_lookahead_schedule_semantics(self):
        # The position[0] is in cash through the first jump (100 -> 120).
        result = evaluate_random_benchmark([100, 120, 120, 120], [0, 1, 0], simulations=20)
        self.assertEqual(result.observed_return_pct, 0)
        self.assertGreater(result.buy_and_hold_return_pct, 0)

    def test_strict_input_validation(self):
        good_closes = [100, 101, 102, 103]
        good_positions = [0, 1, 0]
        bad = [
            (good_closes[:2], [0]),
            (good_closes, [0, 0, 0]),
            (good_closes, [1, 0]),
            ([100, float('nan'), 102, 103], good_positions),
            ([100, float('inf'), 102, 103], good_positions),
            ([100, 0, 102, 103], good_positions),
            (good_closes, [0, 2, 0]),
            (good_closes, [0, 0.5, 0]),
        ]
        for closes, positions in bad:
            with self.subTest(closes=closes, positions=positions):
                with self.assertRaises(ValueError):
                    evaluate_random_benchmark(closes, positions, simulations=10)
        for options in ({'simulations': 0}, {'simulations': 10001}, {'simulations': 0.5},
                        {'fee_bps': -1}, {'slippage_bps': math.nan},
                        {'fee_bps': 5000, 'slippage_bps': 5000}, {'seed': 0.1}):
            with self.subTest(options=options):
                with self.assertRaises(ValueError):
                    evaluate_random_benchmark(good_closes, good_positions, **options)

    def test_seed_does_not_mutate_global_random_state(self):
        random.seed(900)
        expected = random.random()
        random.seed(900)
        evaluate_random_benchmark([100, 99, 101, 102], [0, 1, 0], simulations=10)
        self.assertEqual(random.random(), expected)


if __name__ == '__main__':
    unittest.main()
