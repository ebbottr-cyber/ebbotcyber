# -*- coding: utf-8 -*-
"""BIST100 phase-one symbol contracts: no network or market-data calls."""

import pytest

from src.services.market_symbol_utils import get_suffix_market, market_suffixes, normalize_suffix_market_symbol
from src.services.bist_symbols import (
    BIST100_INDEX_SYMBOL,
    is_bist_equity_symbol,
    normalize_bist100_index_symbol,
    normalize_bist_equity_symbol,
)


@pytest.mark.parametrize(
    ("input_code", "expected"),
    [
        ("THYAO.IS", "THYAO.IS"),
        ("asels.is", "ASELS.IS"),
        ("  AKFYE.is  ", "AKFYE.IS"),
        ("TUPRS.IS", "TUPRS.IS"),
        ("sasa.is", "SASA.IS"),
    ],
)
def test_bist_equities_keep_explicit_yahoo_suffix(input_code, expected):
    assert normalize_bist_equity_symbol(input_code) == expected
    assert is_bist_equity_symbol(input_code) is True


@pytest.mark.parametrize(
    "input_code",
    [
        None, "", " ", "THYAO", "ASELS", "AAPL",
        "XU100.IS", "XU30.IS", "12345.IS",
        "7203.T", "005930.KS", "2330.TW",
        "THYAO.TR", "THYAO.IS.EXTRA", "THYAO..IS",
        "AA.IS", "TOOLONGTICKER.IS",
    ],
)
def test_bist_validation_does_not_guess_other_markets(input_code):
    assert normalize_bist_equity_symbol(input_code) is None
    assert is_bist_equity_symbol(input_code) is False


def test_bist100_benchmark_is_not_the_101st_stock():
    assert normalize_bist100_index_symbol(" xu100.is ") == BIST100_INDEX_SYMBOL
    assert normalize_bist100_index_symbol("XU100") is None
    assert normalize_bist100_index_symbol("THYAO.IS") is None
    assert normalize_bist100_index_symbol("XU030.IS") is None
    assert normalize_bist_equity_symbol(BIST100_INDEX_SYMBOL) is None


def test_bist_equity_is_explicit_turkiye_market_suffix():
    assert get_suffix_market(" THYAO.is ") == "tr"
    assert get_suffix_market("AKFYE.IS") == "tr"
    assert get_suffix_market("XU100.IS") is None
    assert market_suffixes("tr") == ("IS",)
    assert normalize_suffix_market_symbol("thyao.is") == "THYAO.IS"
    assert get_suffix_market("AAPL") is None
    assert get_suffix_market("2330.TW") == "tw"
