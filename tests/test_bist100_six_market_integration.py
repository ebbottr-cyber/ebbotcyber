# -*- coding: utf-8 -*-
"""Cross-market identity boundaries for the BIST100 + six-market draft integration.

No network, SQLite writes, AI models or order gateways are used in these tests.
"""
from datetime import date

import pytest

from data_provider.yfinance_fetcher import YfinanceFetcher
from src.core.trading_calendar import get_market_for_stock, MARKET_EXCHANGE
from src.services.bist100_screener import screen_bist100_from_db
from src.services.bist100_universe import load_bist100_universe
from src.services.six_market_live_smoke import PROBES


DATE = date(2026, 11, 15)


def test_all_seven_market_classifications_are_distinct_and_explicit():
    assert set(MARKET_EXCHANGE) == {"cn", "hk", "us", "jp", "kr", "tw", "tr"}
    assert len(PROBES) == 6
    for sample in PROBES:
        assert get_market_for_stock(sample.code) == sample.market
        assert sample.market != "tr"
    assert get_market_for_stock("THYAO.IS") == "tr"
    assert get_market_for_stock("AKFYE.IS") == "tr"


def test_yahoo_conversion_does_not_rewrite_any_bist_or_foreign_probe():
    convert = YfinanceFetcher()._convert_stock_code
    assert convert("THYAO.IS") == "THYAO.IS"
    assert convert("AKFYE.IS") == "AKFYE.IS"
    for probe in PROBES:
        assert convert(probe.code) == probe.yahoo


def test_bist100_member_selection_never_silently_enrolls_foreign_markets():
    stock_list = set(load_bist100_universe(DATE).symbols)
    assert len(stock_list) == 100
    assert "THYAO.IS" in stock_list
    assert all(spec.code not in stock_list for spec in PROBES)
    assert all(spec.yahoo not in stock_list for spec in PROBES)


@pytest.mark.parametrize("foreign", [
    "600519", "HK00700", "AAPL", "7203.T", "005930.KS", "2330.TW",
])
def test_bist100_screener_rejects_non_members_before_database_read(foreign):
    class ForbiddenDb:
        def get_data_range(self, *_args, **_kwargs):
            pytest.fail("BIST100 screener read a foreign-market ticker")

    with pytest.raises(ValueError, match="BIST100"):
        screen_bist100_from_db(as_of=DATE, symbols=(foreign,), db=ForbiddenDb())
