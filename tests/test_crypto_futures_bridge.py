"""Offline safety checks for EBBot Binance USD-M Futures: no live exchange orders."""
from __future__ import annotations

import time
import unittest
from unittest.mock import AsyncMock, patch

from src.services import crypto_futures_bridge as f

PAIR = "BTC/USDT"
CONTRACT = "BTC/USDT:USDT"
NOW = lambda: int(time.time() * 1000)


def _base(source="Binance public market data"):
    return {"market": "futures", "symbol": CONTRACT, "source": source}


def ticker():
    return {
        **_base(), "last": 80000, "bid": 79999, "ask": 80001,
        "high_24h": 81000, "low_24h": 78000, "base_volume_24h": 2,
        "quote_volume_24h": 160000, "timestamp": NOW(),
    }


def candles():
    return {
        **_base(), "timeframe": "1m", "count": 22,
        "candles": [
            {"timestamp": NOW() - (22 - i) * 60_000,
             "open": 100, "high": 103, "low": 99, "close": 101, "volume": 120}
            for i in range(22)
        ],
    }


def orderbook():
    return {
        **_base("Binance public order book"), "timestamp": NOW(),
        "bids": [[79999, 1], [79998, 2]],
        "asks": [[80001, 1], [80002, 2]],
    }


def funding():
    return {
        **_base("Binance USD-M Futures public market data"),
        "funding_rate": 0.0001, "funding_interval_hours": 8,
        "funding_interval_ms": 28800000, "mark_price": 80000,
        "index_price": 79950, "funding_timestamp": NOW() - 1000,
        "next_funding_timestamp": NOW() + 3600_000,
    }


def interest():
    return {"symbol": "BTCUSDT", "openInterest": "1302.123", "time": NOW()}


class FuturesContractTests(unittest.TestCase):
    def test_ccxt_identity_is_not_spot_identity(self):
        self.assertEqual(f.normalize_pair("btc/usdt"), (PAIR, CONTRACT, "BTCUSDT"))
        for invalid in ("BTC/USDC", "BTC/USDT:USDT", "../BTC/USDT", "BTC/TRY"):
            with self.subTest(invalid=invalid), self.assertRaises(f.FuturesDataError):
                f.normalize_pair(invalid)

    def test_futures_ticker_is_not_spot(self):
        value = f._validate_common(ticker(), "ticker", PAIR, CONTRACT, "1h", 100)
        self.assertEqual(value["market"], "futures")
        self.assertEqual(value["contract"], CONTRACT)
        self.assertEqual(value["symbol"], PAIR)
        self.assertFalse(value["orders_enabled"])
        for changes in (
            {"market": "spot"}, {"symbol": "ETH/USDT:USDT"}, {"last": None},
            {"timestamp": NOW() - 500_000}, {"ask": 79998},
        ):
            with self.subTest(changes=changes), self.assertRaises(f.FuturesDataError):
                f._validate_common({**ticker(), **changes}, "ticker", PAIR, CONTRACT, "1h", 100)

    def test_real_candle_and_depth_contracts(self):
        c = f._validate_common(candles(), "ohlcv", PAIR, CONTRACT, "1m", 100)
        self.assertEqual(c["quality"], "ok")
        self.assertEqual(c["market"], "futures")
        d = f._validate_common(orderbook(), "orderbook", PAIR, CONTRACT, "1h", 20)
        self.assertGreater(d["bid_quote_depth"], 0)
        self.assertTrue(d["orders_enabled"] is False)
        broken = candles()
        broken["candles"][0]["high"] = 1
        with self.assertRaises(f.FuturesDataError):
            f._validate_common(broken, "ohlcv", PAIR, CONTRACT, "1m", 100)
        crossed = orderbook()
        crossed["asks"][0][0] = 79998
        with self.assertRaises(f.FuturesDataError):
            f._validate_common(crossed, "orderbook", PAIR, CONTRACT, "1h", 20)

    def test_funding_checks_mark_index_rate_interval_and_market(self):
        value = f.validate_funding(funding(), CONTRACT, PAIR)
        self.assertEqual(value["funding_rate"], 0.0001)
        self.assertEqual(value["quality"], "unknown")  # settlement != observation time
        for patch_data in (
            {"mark_price": 0}, {"index_price": -1}, {"funding_rate": float("nan")},
            {"funding_rate": .5}, {"funding_interval_hours": 3},
            {"funding_interval_ms": 1000}, {"market": "spot"},
            {"symbol": "BTC/USDT"}, {"source": "untrusted"},
        ):
            with self.subTest(data=patch_data), self.assertRaises(f.FuturesDataError):
                f.validate_funding({**funding(), **patch_data}, CONTRACT, PAIR)

    def test_open_interest_is_actual_binance_decimal_with_timestamp(self):
        value = f.validate_open_interest(interest(), PAIR, "BTCUSDT")
        self.assertEqual(value["open_interest"], 1302.123)
        self.assertEqual(value["unit"], "BTC")
        self.assertEqual(value["source"], "Binance USD-M Futures public openInterest")
        for changes in (
            {"openInterest": None}, {"openInterest": "-1"}, {"openInterest": "NaN"},
            {"openInterest": "Infinity"}, {"openInterest": "not a price"},
            {"symbol": "ETHUSDT"}, {"time": NOW() - 600_000},
            {"time": NOW() + 600_000},
        ):
            with self.subTest(data=changes), self.assertRaises(f.FuturesDataError):
                f.validate_open_interest({**interest(), **changes}, PAIR, "BTCUSDT")

    def test_futures_routes_never_include_paper_order_paths(self):
        for dataset, end in (
            ("ticker", "ticker"), ("ohlcv", "ohlcv"),
            ("orderbook", "orderbook"), ("funding", "funding-rate"),
        ):
            path, params = f._route(dataset, CONTRACT, "1h", 100)
            self.assertEqual(path, "/api/v1/markets/futures/" + end)
            self.assertEqual(params["symbol"], CONTRACT)
            self.assertNotIn("paper", path)
            self.assertNotIn("order", path.replace("orderbook", ""))

    def test_stale_cached_observation_rejected(self):
        sample = {
            "quality": "ok", "timestamp": NOW() - 200_000,
            "last": 80000,
        }
        self.assertFalse(f._still_fresh(sample))


class FuturesGatewayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        f._CACHE.clear()
        f._FAILURES.clear()

    async def test_read_only_futures_funding_and_cache(self):
        method = AsyncMock(return_value=funding())
        with patch.object(f, "_connection_settings", return_value=("http://127.0.0.1:8001", "r"*40)), patch.object(
            f, "_bounded_get", method
        ), patch.dict("os.environ", {"TRADING_ENABLED": "false"}):
            first = await f.futures_data("funding", PAIR)
            second = await f.futures_data("funding", PAIR)
        self.assertFalse(first["cached"])
        self.assertTrue(second["cached"])
        self.assertEqual(method.await_count, 1)
        self.assertEqual(method.await_args.args[0], "http://127.0.0.1:8001/api/v1/markets/futures/funding-rate")
        self.assertEqual(method.await_args.kwargs["params"]["symbol"], CONTRACT)

    async def test_open_interest_uses_fixed_public_domain_without_private_key(self):
        method = AsyncMock(return_value=interest())
        with patch.object(f, "_bounded_get", method), patch.dict("os.environ", {"TRADING_ENABLED": "false"}):
            result = await f.futures_data("open-interest", PAIR)
        self.assertFalse(result["orders_enabled"])
        self.assertEqual(result["open_interest"], 1302.123)
        self.assertEqual(method.await_args.args[0], "https://fapi.binance.com/fapi/v1/openInterest")
        self.assertEqual(method.await_args.kwargs["params"], {"symbol": "BTCUSDT"})
        self.assertNotIn("X-API-Key", method.await_args.kwargs.get("headers", {}))

    async def test_live_trading_flag_closes_all_market_feeds(self):
        with patch.dict("os.environ", {"TRADING_ENABLED": "true"}):
            with self.assertRaises(f.FuturesDataError):
                await f.futures_data("open-interest", PAIR)

    async def test_stale_open_interest_is_never_cached_or_shown(self):
        mock = AsyncMock(return_value={**interest(), "time": NOW() - 3600_000})
        with patch.object(f, "_bounded_get", mock), patch.dict("os.environ", {"TRADING_ENABLED": "false"}):
            with self.assertRaises(f.FuturesDataError):
                await f.futures_data("open-interest", PAIR)
        self.assertFalse(f._CACHE)


if __name__ == "__main__":
    unittest.main()
