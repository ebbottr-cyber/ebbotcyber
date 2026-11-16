"""Offline checks for CoinGecko Top100; no network, no trades."""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from src.services import coingecko_top100 as cg


class CoinGeckoTop100Test(unittest.TestCase):
    def setUp(self):
        cg._roster = None
        cg._roster_time = 0
        cg._technical_cache.clear()

    def test_top100_keeps_ids_and_symbols_separate(self):
        raw = [{
            "id": f"test-coin-{i}", "symbol": "same", "name": f"Coin {i}",
            "market_cap_rank": i + 1, "current_price": 1.5,
            "market_cap": 100000 - i, "total_volume": 1000,
            "price_change_percentage_24h": 2.0,
        } for i in range(100)]
        with patch.object(cg, "_fetch", return_value=raw) as fetch:
            result = cg.top100()
            cached = cg.top100()
        self.assertEqual(result["count"], 100)
        self.assertEqual(len(result["coins"]), 100)
        self.assertEqual(result["coins"][0]["symbol"], "SAME")
        self.assertEqual(result["coins"][0]["id"], "test-coin-0")
        self.assertEqual(result["coins"][-1]["market_cap_rank"], 100)
        self.assertTrue(cached["cached"])
        fetch.assert_called_once()

    def test_rejects_incomplete_or_duplicate_roster(self):
        with self.assertRaises(cg.CoinGeckoError):
            cg._normalize_roster([{"id": "bitcoin"}])
        duplicate = [{"id": "same", "symbol": "S", "name": "Duplicate"} for _ in range(100)]
        with self.assertRaises(cg.CoinGeckoError):
            cg._normalize_roster(duplicate)

    def test_builds_real_ohlc_daily_bars_without_fabricating_volume(self):
        today = datetime.now(timezone.utc).date()
        candles, volume = [], []
        for offset in range(30, 0, -1):
            day = today - timedelta(days=offset)
            start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
            first = (start + timedelta(hours=4)).timestamp() * 1000
            last = (start + timedelta(hours=20)).timestamp() * 1000
            candles.extend([[first, 100, 102, 99, 101], [last, 101, 103, 100, 102]])
            volume.append([last, 500.0])
        daily = cg.daily_bars(candles, {"total_volumes": volume})
        self.assertEqual(len(daily), 30)
        self.assertEqual(daily.iloc[0]["high"], 103)
        self.assertEqual(daily.iloc[0]["close"], 102)
        with self.assertRaises(cg.CoinGeckoError):
            cg.daily_bars(candles, {"total_volumes": volume[:10]})

    def test_unknown_coin_never_fetches_history(self):
        with patch.object(cg, "top100", return_value={"coins": [{"id": "bitcoin"}]}):
            with patch.object(cg, "_fetch") as fetch:
                with self.assertRaises(cg.CoinGeckoError):
                    cg.analyze_coin("unknown")
                with self.assertRaises(cg.CoinGeckoError):
                    cg.analyze_coin("../bitcoin")
                fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
