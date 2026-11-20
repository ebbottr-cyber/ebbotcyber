"""Contracts for the scoped PR113 + TR data-quality overlay, without trades/network.

Unlike a broad historical PR120 merge, this overlay preserves PR113's existing
portfolio display-rate endpoint, additively exposes TCMB's indicative reference,
and does not change portfolio accounting/execution or the React FX API.
"""
from __future__ import annotations

from datetime import date
from unittest.mock import patch

from api.v1.endpoints import portfolio
from api.v1.schemas.portfolio import PortfolioDisplayFxResponse, PortfolioTryDisplayResponse
from src.services.tr_market_overview_service import INSTRUMENTS, quote_from_rows


def test_existing_portfolio_fx_display_and_refresh_routes_are_preserved():
    paths = {(x.path, tuple(sorted(x.methods))) for x in portfolio.router.routes}
    assert ("/fx/display-rates", ("GET",)) in paths
    assert ("/fx/try-display", ("GET",)) in paths
    assert ("/fx/refresh", ("POST",)) in paths
    assert len([x for x in paths if x[0] == "/fx/display-rates"]) == 1
    assert len([x for x in paths if x[0] == "/fx/try-display"]) == 1


def test_existing_display_contract_untouched_and_no_rate_substitution():
    with patch.object(
        portfolio, "get_try_display_rates",
        return_value={"status": "unavailable", "source": "unavailable"},
    ) as provider:
        result = portfolio.get_display_fx_rates()
    assert isinstance(result, PortfolioDisplayFxResponse)
    assert result.status == "unavailable"
    assert result.usd_try is None
    assert result.source == "unavailable"
    assert provider.call_count == 1


def test_new_tcmb_reference_readonly_and_kept_separate_from_portfolio_accounting():
    reference = {
        "available": True, "source": "TCMB",
        "rate_kind": "indicative_forex_selling", "as_of_date": "2026-11-20",
        "quotes": [{
            "source": "TCMB", "source_currency": "USD", "target_currency": "TRY",
            "source_unit": 1, "try_per_unit": 50.0, "as_of_date": "2026-11-20",
        }],
    }
    with patch.object(portfolio, "get_tcmb_try_display_quotes", return_value=reference) as tcmb, \
         patch.object(portfolio, "PortfolioService", side_effect=AssertionError("ledger touched")), \
         patch.object(portfolio, "get_try_display_rates", side_effect=AssertionError("fallback used")):
        result = portfolio.get_try_display_quotes()
    assert isinstance(result, PortfolioTryDisplayResponse)
    assert result.source == "TCMB"
    assert result.rate_kind == "indicative_forex_selling"
    assert len(result.quotes) == 1
    assert result.quotes[0].try_per_unit == 50.0
    assert tcmb.call_count == 1


def test_market_quotes_keep_fixed_symbols_and_boolean_price_is_unavailable():
    assert [x[2] for x in INSTRUMENTS] == ["XU100.IS", "XU030.IS", "TRY=X", "EURTRY=X"]
    q = quote_from_rows(
        "usdtry", "USD/TRY", "TRY=X", "TRY",
        [(date(2026, 11, 19), True)], date(2026, 11, 20),
    )
    assert q["status"] == "unavailable"
    assert q["price"] is None
    assert q["change_pct"] is None


def test_huge_price_ratio_not_promoted_to_nonfinite_change():
    q = quote_from_rows(
        "usdtry", "USD/TRY", "TRY=X", "TRY",
        [(date(2026, 11, 18), 1e-300), (date(2026, 11, 19), 1e300)],
        date(2026, 11, 20),
    )
    assert q["status"] == "ready"
    assert q["change_pct"] is None
