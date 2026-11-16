# -*- coding: utf-8 -*-
"""Conservative Xetra .DE identification and Yahoo routing, without live orders."""
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
import pytest

from data_provider.base import DataFetcherManager, _market_tag, normalize_stock_code
from data_provider.yfinance_fetcher import YfinanceFetcher
from src.core import trading_calendar
from src.market_context import detect_market, get_market_guidelines, get_market_role
from src.services.market_symbol_utils import get_suffix_market, market_suffixes
from src.services.stock_code_utils import normalize_code, is_code_like, resolve_daily_stock_identity
from src.services.stock_list_parser import parse_analysis_target, ParseStatus


@pytest.mark.parametrize("raw", ["SAP.DE", " sap.de ", "BMW.DE", "VOW3.DE", "SIE.DE", "MUV2.DE"])
def test_xetra_equities_preserve_market_and_explicit_suffix(raw):
    code = raw.strip().upper()
    assert get_suffix_market(raw) == "de"
    parsed = parse_analysis_target(raw)
    assert parsed.asset_type == ParseStatus.STOCK
    assert parsed.exchange == "DE"
    assert parsed.canonical_id == code
    assert normalize_code(raw) == code
    assert normalize_stock_code(raw).upper() == code
    assert _market_tag(code) == "de"
    assert detect_market(code) == "de"
    assert trading_calendar.get_market_for_stock(code) == "de"
    assert YfinanceFetcher()._convert_stock_code(raw) == code
    assert is_code_like(code)
    identity = resolve_daily_stock_identity(raw)
    assert identity is not None and identity.market == "de" and identity.refill_code == code


@pytest.mark.parametrize("raw", ["SAP", "BMW", "VOW3", "1234.DE", "SAP.DE.Z", "SAP.DEX", "BAD-NAME.DE"])
def test_germany_does_not_infer_exchange_from_ambiguous_or_invalid_codes(raw):
    assert get_suffix_market(raw) is None
    assert get_suffix_market("AAPL") is None
    assert get_suffix_market("THYAO.IS") == "tr"
    if raw.endswith(".DE"):
        parsed = parse_analysis_target(raw)
        assert parsed.asset_type == ParseStatus.UNSUPPORTED


def test_xetra_daily_route_rejects_cn_sources():
    fetchers = [
        SimpleNamespace(name="AkshareFetcher"),
        SimpleNamespace(name="YfinanceFetcher"),
        SimpleNamespace(name="EfinanceFetcher"),
        SimpleNamespace(name="UnknownCustomFetcher"),
    ]
    selected = DataFetcherManager._filter_daily_fetchers_for_market(fetchers, "de")
    assert [item.name for item in selected] == ["YfinanceFetcher"]
    assert market_suffixes("de") == ("DE",)


def test_xetra_quotes_never_try_cn_provider_fallback():
    manager = DataFetcherManager(fetchers=[])
    with (
        patch("src.config.get_config", return_value=SimpleNamespace(enable_realtime_quote=True)),
        patch.object(manager, "_try_fetcher_quote", return_value=None) as fetch_quote,
        patch.object(manager, "_get_cn_index_realtime_quote") as cn_index,
    ):
        assert manager.get_realtime_quote("sap.de") is None
    fetch_quote.assert_called_once_with("sap.de".upper(), "YfinanceFetcher")
    cn_index.assert_not_called()


def test_xetra_prompt_is_european_and_eur_not_chinese():
    assert "Xetra" in get_market_role("SAP.DE", lang="tr")
    guidance = get_market_guidelines("SAP.DE", lang="tr")
    assert "EUR" in guidance and "Europe/Berlin" in guidance
    assert "Do not apply China" in guidance


def test_xetra_calendar_is_berlin_and_uses_xetr():
    assert trading_calendar.MARKET_EXCHANGE["de"] == "XETR"
    assert trading_calendar.MARKET_TIMEZONE["de"] == "Europe/Berlin"
    sessions = pd.DatetimeIndex(["2024-10-02", "2024-10-04"], tz="UTC")
    fake = SimpleNamespace(sessions_in_range=lambda start, end: sessions)
    with patch.object(trading_calendar, "_XCALS_AVAILABLE", True), patch.object(
        trading_calendar.xcals, "get_calendar", return_value=fake
    ) as getter:
        result = trading_calendar.get_trading_dates("de", date(2024, 10, 2), date(2024, 10, 4))
    getter.assert_called_once_with("XETR")
    assert result.equals(pd.DatetimeIndex(["2024-10-02", "2024-10-04"]))
