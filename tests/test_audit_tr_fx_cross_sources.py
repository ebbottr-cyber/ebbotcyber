"""No-network tests of informational cross-provider FX comparisons and warnings."""
from __future__ import annotations

from copy import deepcopy
from datetime import date
import json
import math

import pytest

from scripts.audit_tr_fx_cross_sources import compare_observations, MARKET_SOURCE


def sample_report(day="2026-11-20"):
    return {
        "as_of_local_date": "2026-11-20",
        "research_only": True, "prices_executable": False,
        "orders": 0, "paper_fills": 0, "journal_writes": 0,
        "paper_trading_enabled": False, "live_trading_enabled": False,
        "market_daily": {"checks": [
            {"key": "bist100", "symbol": "XU100.IS", "source": MARKET_SOURCE,
             "price_date": day, "price": 10000.0, "status": "observed_delayed_daily",
             "indicative_only": True, "executable_quote": False},
            {"key": "bist30", "symbol": "XU030.IS", "source": MARKET_SOURCE,
             "price_date": day, "price": 12000.0, "status": "observed_delayed_daily",
             "indicative_only": True, "executable_quote": False},
            {"key": "usdtry", "symbol": "TRY=X", "source": MARKET_SOURCE,
             "price_date": day, "price": 50.4, "status": "observed_delayed_daily",
             "indicative_only": True, "executable_quote": False},
            {"key": "eurtry", "symbol": "EURTRY=X", "source": MARKET_SOURCE,
             "price_date": day, "price": 55.1, "status": "observed_delayed_daily",
             "indicative_only": True, "executable_quote": False},
        ]},
        "official_tcmb": {"checks": [
            {"currency": "USD", "target_currency": "TRY",
             "bulletin_date": day, "try_per_unit": 50.0,
             "source": "TCMB daily ForexSelling", "status": "observed_official_indicative",
             "executable_quote": False},
            {"currency": "EUR", "target_currency": "TRY",
             "bulletin_date": day, "try_per_unit": 55.0,
             "source": "TCMB daily ForexSelling", "status": "observed_official_indicative",
             "executable_quote": False},
            {"currency": "CNY", "target_currency": "TRY",
             "bulletin_date": day, "try_per_unit": 7.5,
             "source": "TCMB daily ForexSelling", "status": "observed_official_indicative",
             "executable_quote": False},
        ]},
    }


def pairs(r):
    return {p["pair"]: p for p in r["fx_pairs"]}


def test_both_sources_observed_but_different_quote_kinds_not_trade_validated():
    report = compare_observations(sample_report())
    usd = pairs(report)["USD/TRY"]
    assert usd["status"] == "difference_recorded_not_validation"
    assert usd["absolute_difference_pct_of_tcmb"] == 0.8
    assert usd["sources_interchangeable"] is False
    assert report["same_date_is_not_same_time"]
    assert all(row["independently_confirmed"] is False for row in report["bist_indices"])
    assert all(row["independent_second_source"] == "not_configured" for row in report["bist_indices"])
    assert report["cny"]["independent_second_source"] == "not_configured"
    assert not report["prices_executable"]
    assert report["orders"] == report["paper_fills"] == report["journal_writes"] == 0


def test_large_difference_flag_is_informational_only():
    r = sample_report()
    r["market_daily"]["checks"][2]["price"] = 52.5  # +5% vs 50
    out = compare_observations(r)
    assert pairs(out)["USD/TRY"]["status"] == "difference_for_manual_review"
    assert pairs(out)["USD/TRY"]["absolute_difference_pct_of_tcmb"] == 5.0
    assert "USD_indicative_difference_review" in out["alerts"]
    assert out["threshold_purpose"] == "manual_review_not_trade_validation"


def test_mismatched_source_dates_do_not_compute_a_diagnostic_percentage():
    r = sample_report()
    r["official_tcmb"]["checks"][0]["bulletin_date"] = "2026-11-19"
    x = pairs(compare_observations(r))["USD/TRY"]
    assert x["status"] == "different_publication_dates"
    assert x["absolute_difference_pct_of_tcmb"] is None


def test_source_outage_never_uses_other_currency_or_averages():
    r = sample_report()
    r["market_daily"]["checks"] = [x for x in r["market_daily"]["checks"] if x["key"] != "usdtry"]
    r["official_tcmb"]["checks"] = [x for x in r["official_tcmb"]["checks"] if x["currency"] != "EUR"]
    report = compare_observations(r)
    for pair in pairs(report).values():
        assert pair["status"] == "insufficient_source_evidence"
        assert pair["absolute_difference_pct_of_tcmb"] is None
    assert "USD_comparison_unavailable" in report["alerts"]
    assert "EUR_comparison_unavailable" in report["alerts"]


def test_lag_watch_does_not_relabel_daily_or_central_bank_rates_as_current():
    r = sample_report(day="2026-11-17")
    out = compare_observations(r)
    assert "USD_yahoo_daily_lag_watch" in out["alerts"]
    assert "USD_tcmb_bulletin_lag_watch" in out["alerts"]
    assert "bist100_yahoo_daily_lag_watch" in out["alerts"]
    assert "CNY_tcmb_bulletin_lag_watch" in out["alerts"]
    assert pairs(out)["USD/TRY"]["yahoo_daily_age_calendar_days"] == 3
    assert pairs(out)["USD/TRY"]["tcmb_age_calendar_days"] == 3
    assert not out["prices_executable"]


def test_future_and_expired_inputs_are_unavailable():
    for day in ("2026-11-21", "2026-11-01"):
        out = compare_observations(sample_report(day))
        assert all(x["status"] == "insufficient_source_evidence" for x in out["fx_pairs"])
        assert all(x["yahoo_daily_date"] is None for x in out["fx_pairs"])
        assert all(x["tcmb_forex_selling_date"] is None for x in out["fx_pairs"])
        assert out["cny"]["tcmb_date"] is None
        assert all(x["yahoo_daily_date"] is None for x in [])  # No guessed dates.


def test_duplicate_quotes_nonfinite_numeric_and_bool_fail_closed():
    r = sample_report()
    r["market_daily"]["checks"].append(deepcopy(r["market_daily"]["checks"][2]))
    r["official_tcmb"]["checks"].append(deepcopy(r["official_tcmb"]["checks"][0]))
    r["market_daily"]["checks"][3]["price"] = float("nan")
    r["official_tcmb"]["checks"][1]["try_per_unit"] = True
    out = compare_observations(r)
    assert all(x["absolute_difference_pct_of_tcmb"] is None for x in out["fx_pairs"])
    assert all(x["status"] == "insufficient_source_evidence" for x in out["fx_pairs"])
    json.dumps(out, allow_nan=False)


def test_invalid_source_metadata_blocks_price_comparison():
    r = sample_report()
    r["market_daily"]["checks"][2]["source"] = "untrusted"
    r["official_tcmb"]["checks"][0]["executable_quote"] = True
    out = compare_observations(r)
    assert pairs(out)["USD/TRY"]["status"] == "insufficient_source_evidence"
    assert pairs(out)["USD/TRY"]["absolute_difference_pct_of_tcmb"] is None


def test_inf_divergence_never_serializes_nan():
    r = sample_report()
    r["market_daily"]["checks"][2]["price"] = 1e300
    r["official_tcmb"]["checks"][0]["try_per_unit"] = 1e-300
    out = compare_observations(r)
    assert pairs(out)["USD/TRY"]["absolute_difference_pct_of_tcmb"] is None
    json.dumps(out, allow_nan=False)


@pytest.mark.parametrize("invalid", [
    None, {}, {"as_of_local_date": "unparsable"},
    {"as_of_local_date": "2026-11-20", "research_only": False, "prices_executable": False},
])
def test_malformed_or_non_research_reports_are_blocked(invalid):
    with pytest.raises(ValueError):
        compare_observations(invalid)


def test_order_or_paper_activity_is_refused_instead_of_diagnostic():
    for key, invalid in [
        ("orders", 1), ("paper_fills", 1), ("journal_writes", 1),
        ("paper_trading_enabled", True), ("live_trading_enabled", True),
    ]:
        r = sample_report()
        r[key] = invalid
        with pytest.raises(ValueError):
            compare_observations(r)


def test_unavailable_all_providers_never_fabricates_bist_comparison():
    r = sample_report()
    r["market_daily"]["checks"] = []
    r["official_tcmb"]["checks"] = []
    out = compare_observations(r)
    assert out["alerts"]
    assert all(x["absolute_difference_pct_of_tcmb"] is None for x in out["fx_pairs"])
    assert all(x["independently_confirmed"] is False for x in out["bist_indices"])
    assert out["cny"]["tcmb_date"] is None
