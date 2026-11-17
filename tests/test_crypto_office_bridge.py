"""Offline safety checks for EBBot's isolated read-only crypto bridge."""
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from src.services.crypto_office_bridge import (
    CryptoOfficeUnavailable,
    _connection_settings,
    validate_dashboard,
)


def sample():
    return {
        "schema_version": "1.1",
        "mode": "paper_only",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "application": {"name": "Trading Office", "version": "6.9.3"},
        "safety": {"real_exchange_orders": False, "live_trading_enabled": False},
        "portfolio": {"combined": {"valuation_complete": True, "equity": 20000.0},
                      "spot": {}, "futures": {}, "open_positions": []},
        "risk": {}, "performance": {}, "validation": {},
        "agents": {}, "strategies": {}, "operations": {},
    }


class CryptoOfficeBridgeTests(unittest.TestCase):
    def test_valid_paper_only_contract(self):
        self.assertEqual(validate_dashboard(sample())["schema_version"], "1.1")

    def test_missing_market_prices_must_be_null_not_zero(self):
        data = sample()
        data["portfolio"]["combined"] = {"valuation_complete": False, "equity": None}
        self.assertIsNone(validate_dashboard(data)["portfolio"]["combined"]["equity"])
        data["portfolio"]["combined"]["equity"] = 0
        with self.assertRaises(CryptoOfficeUnavailable):
            validate_dashboard(data)

    def test_actual_equity_must_be_finite_and_not_negative(self):
        for invalid in (float("nan"), float("inf"), -12, True, "20000", None):
            with self.subTest(invalid=invalid):
                data = sample()
                data["portfolio"]["combined"]["equity"] = invalid
                with self.assertRaises(CryptoOfficeUnavailable):
                    validate_dashboard(data)

    def test_never_accept_live_order_flags(self):
        for key in ("real_exchange_orders", "live_trading_enabled"):
            data = sample()
            data["safety"][key] = True
            with self.assertRaises(CryptoOfficeUnavailable):
                validate_dashboard(data)

    def test_rejects_stale_future_or_timezone_naive_reports(self):
        for stamp in (
            (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
            (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            "2026-11-17T10:00:00",
        ):
            data = sample()
            data["generated_at"] = stamp
            with self.assertRaises(CryptoOfficeUnavailable):
                validate_dashboard(data)

    def test_rejects_credentials_in_any_nested_section(self):
        for sensitive in (
            {"api_key": "not even a real secret"},
            {"meta": [{"private_key": True}]},
            {"comment": "Bearer abcdefghijklmnop123456"},
        ):
            data = sample()
            data["operations"] = sensitive
            with self.assertRaises(CryptoOfficeUnavailable):
                validate_dashboard(data)

    def test_rejects_missing_sections_and_future_versions(self):
        data = sample()
        data["schema_version"] = "2.0"
        with self.assertRaises(CryptoOfficeUnavailable):
            validate_dashboard(data)
        data = sample()
        del data["risk"]
        with self.assertRaises(CryptoOfficeUnavailable):
            validate_dashboard(data)

    def test_no_remote_or_unsafe_proxy_url(self):
        settings = {
            "TRADING_ENABLED": "false",
            "TRADING_OFFICE_READ_API_KEY": "r" * 40,
        }
        for endpoint in (
            "http://169.254.169.254:8001",
            "https://malicious.example.com",
            "http://127.0.0.1:8001/any/other/path",
            "http://user:password@localhost:8001",
            "http://localhost:abc",
            "http://localhost:8001?data=1",
        ):
            with self.subTest(endpoint=endpoint), patch.dict(os.environ, {
                **settings, "TRADING_OFFICE_URL": endpoint,
            }):
                with self.assertRaises(CryptoOfficeUnavailable):
                    _connection_settings()

    def test_local_proxy_needs_32_char_key_and_trading_disabled(self):
        with patch.dict(os.environ, {
            "TRADING_OFFICE_URL": "http://127.0.0.1:8001",
            "TRADING_OFFICE_READ_API_KEY": "r" * 40,
            "TRADING_ENABLED": "false",
        }):
            self.assertEqual(_connection_settings()[0], "http://127.0.0.1:8001")
        with patch.dict(os.environ, {
            "TRADING_OFFICE_URL": "http://127.0.0.1:8001",
            "TRADING_OFFICE_READ_API_KEY": "short",
            "TRADING_ENABLED": "false",
        }):
            with self.assertRaises(CryptoOfficeUnavailable):
                _connection_settings()
        with patch.dict(os.environ, {
            "TRADING_OFFICE_URL": "http://127.0.0.1:8001",
            "TRADING_OFFICE_READ_API_KEY": "r" * 40,
            "TRADING_ENABLED": "true",
        }):
            with self.assertRaises(CryptoOfficeUnavailable):
                _connection_settings()


if __name__ == "__main__":
    unittest.main()
