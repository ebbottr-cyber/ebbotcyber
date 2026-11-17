"""Offline tests: EBBot Binance Spot data is public, read-only and fail-closed."""
from __future__ import annotations

import time
import unittest
from unittest.mock import AsyncMock, patch

from src.services import crypto_spot_bridge as spot

SYMBOL = "BTC/USDT"


def ticker():
    return {
        "market": "spot", "symbol": SYMBOL, "source": "Binance public market data",
        "last": 45000.5, "bid": 45000.0, "ask": 45001.0,
        "high_24h": 46000.0, "low_24h": 44000.0,
        "base_volume_24h": 100, "quote_volume_24h": 5000000,
        "timestamp": int(time.time() * 1000),
    }


def candles():
    now = int(time.time() * 1000)
    rows = []
    for i in range(22, 0, -1):
        rows.append({
            "timestamp": now - i * 60_000,
            "open": 99.0, "high": 103.0, "low": 98.0,
            "close": 102.0, "volume": 100.0,
        })
    return {
        "market": "spot", "symbol": SYMBOL, "source": "Binance public market data",
        "timeframe": "1m", "count": len(rows), "candles": rows,
    }


def orderbook():
    return {
        "market": "spot", "symbol": SYMBOL, "source": "Binance public order book",
        "timestamp": int(time.time() * 1000),
        "bids": [[45000.0, 2.0], [44999.0, 1.0]],
        "asks": [[45001.0, 3.0], [45002.0, 1.0]],
    }


class SpotContractTests(unittest.TestCase):
    def test_valid_ticker_and_no_orders(self):
        result = spot.validate_ticker(ticker(), SYMBOL)
        self.assertEqual(result["quality"], "ok")
        self.assertFalse(result["orders_enabled"])
        self.assertEqual(result["last"], 45000.5)

    def test_missing_timestamp_is_unknown_not_now(self):
        data = ticker()
        data["timestamp"] = None
        result = spot.validate_ticker(data, SYMBOL)
        self.assertIsNone(result["timestamp"])
        self.assertEqual(result["quality"], "unknown")

    def test_stale_invalid_wrong_market_and_missing_data_fail(self):
        for modification in (
            {"timestamp": int((time.time() - 1000) * 1000)},
            {"last": 0},
            {"last": None},
            {"market": "futures"},
            {"source": "untrusted"},
            {"bid": 50000.0, "ask": 45000.0},
            {"last": float("nan")},
        ):
            with self.subTest(modification=modification):
                with self.assertRaises(spot.SpotDataError):
                    spot.validate_ticker({**ticker(), **modification}, SYMBOL)

    def test_candles_are_real_sorted_valid_and_fresh(self):
        data = candles()
        result = spot.validate_ohlcv(data, SYMBOL, "1m", 100)
        self.assertEqual(result["count"], len(data["candles"]))
        self.assertEqual(result["last_candle_timestamp"], data["candles"][-1]["timestamp"])
        self.assertEqual(result["quality"], "ok")
        data["candles"][5]["high"] = 90
        with self.assertRaises(spot.SpotDataError):
            spot.validate_ohlcv(data, SYMBOL, "1m", 100)

    def test_reject_duplicate_missing_and_outdated_candles(self):
        for scenario in ("duplicate", "missing", "stale", "wrong_timeframe"):
            data = candles()
            if scenario == "duplicate":
                data["candles"][3]["timestamp"] = data["candles"][2]["timestamp"]
            if scenario == "missing":
                del data["candles"][0]["volume"]
            if scenario == "stale":
                for row in data["candles"]:
                    row["timestamp"] -= 10 * 60_000
            if scenario == "wrong_timeframe":
                data["timeframe"] = "4h"
            with self.subTest(scenario=scenario), self.assertRaises(spot.SpotDataError):
                spot.validate_ohlcv(data, SYMBOL, "1m", 100)

    def test_orderbook_cross_and_missing_levels_fail(self):
        valid = spot.validate_orderbook(orderbook(), SYMBOL, 20)
        self.assertEqual(valid["quality"], "ok")
        self.assertTrue(valid["bid_quote_depth"] > 0)
        self.assertTrue(valid["ask_quote_depth"] > 0)
        for scenario in ("crossed", "unsorted", "zero", "missing", "future"):
            book = orderbook()
            if scenario == "crossed":
                book["bids"][0][0] = book["asks"][0][0]
            if scenario == "unsorted":
                book["asks"].reverse()
            if scenario == "zero":
                book["bids"][0][0] = 0
            if scenario == "missing":
                book["bids"] = []
            if scenario == "future":
                book["timestamp"] += 60 * 60 * 1000
            with self.subTest(scenario=scenario), self.assertRaises(spot.SpotDataError):
                spot.validate_orderbook(book, SYMBOL, 20)

    def test_symbol_cannot_be_route_injection_or_unlisted_quote(self):
        for value in ("BTCUSDT", "BTC/TRY", "BTC/USDT?hack=x", "../BTC/USDT", "BTC/USDT%2F", "BT C/USDT"):
            with self.subTest(value=value), self.assertRaises(spot.SpotDataError):
                spot._params("ticker", value, "1h", 100)
        self.assertEqual(spot._params("ticker", SYMBOL, "1h", 100)[0],
                         "/api/v1/markets/spot/ticker")


class SpotGatewayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        spot._CACHE.clear()

    async def test_only_public_read_and_cache(self):
        mock_request = AsyncMock(return_value=ticker())
        with patch.object(spot, "_connection_settings", return_value=("http://127.0.0.1:8001", "r" * 40)), patch.object(
            spot, "_request", mock_request
        ):
            first = await spot.spot_data("ticker", SYMBOL)
            second = await spot.spot_data("ticker", SYMBOL)
        self.assertFalse(first["cached"])
        self.assertTrue(second["cached"])
        self.assertEqual(mock_request.await_count, 1)
        args = mock_request.await_args.args
        self.assertEqual(args[0], "/api/v1/markets/spot/ticker")
        self.assertEqual(args[1], {"symbol": SYMBOL})

    async def test_unavailable_data_does_not_poison_cache(self):
        with patch.object(spot, "_connection_settings", return_value=("http://127.0.0.1:8001", "r" * 40)), patch.object(
            spot, "_request", AsyncMock(return_value={**ticker(), "last": None})
        ):
            with self.assertRaises(spot.SpotDataError):
                await spot.spot_data("ticker", SYMBOL)
        self.assertFalse(spot._CACHE)


if __name__ == "__main__":
    unittest.main()
