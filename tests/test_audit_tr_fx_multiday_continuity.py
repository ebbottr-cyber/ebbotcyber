"""Completely synthetic fixtures: never represented as market observations."""
from __future__ import annotations

from copy import deepcopy
from datetime import date
import json

import pytest

from scripts.audit_tr_fx_multiday_continuity import summarize_continuity
from src.services.tr_market_overview_service import SOURCE as YAHOO_SOURCE


def sample(day: str, *, hour: int = 12) -> dict:
    return {
        "status": "READ_ONLY_OBSERVATION",
        "observed_at_istanbul": f"{day}T{hour:02d}:00:00+03:00",
        "as_of_local_date": day,
        "research_only": True, "prices_executable": False,
        "paper_trading_enabled": False, "live_trading_enabled": False,
        "scheduler_enabled": False,
        "orders": 0, "paper_fills": 0, "journal_writes": 0,
        "market_daily": {"checks": [
            {"key": key, "symbol": symbol, "status": "observed_delayed_daily",
             "price": 100.0, "price_date": day, "source": YAHOO_SOURCE,
             "indicative_only": True, "executable_quote": False}
            for key, symbol in (
                ("bist100", "XU100.IS"),
                ("bist30", "XU030.IS"),
                ("usdtry", "TRY=X"),
                ("eurtry", "EURTRY=X"),
            )
        ]},
        "official_tcmb": {"checks": [
            {"currency": code, "target_currency": "TRY",
             "status": "observed_official_indicative", "source": "TCMB daily ForexSelling",
             "try_per_unit": 50.0, "bulletin_date": day, "executable_quote": False}
            for code in ("USD", "EUR", "CNY")
        ]},
    }


def test_two_observations_on_one_day_are_not_multiday_continuity():
    r = summarize_continuity([
        sample("2026-11-20", hour=11),
        sample("2026-11-20", hour=16),
    ])
    assert r["status"] == "INSUFFICIENT_DISTINCT_DATES"
    assert r["total_observations"] == 2
    assert r["distinct_observation_dates"] == 1
    assert r["daily_evidence"][0]["observation_count"] == 2
    assert r["daily_evidence"][0]["complete_indicative_source_coverage"]
    assert r["expected_dates"] is None
    assert r["missing_expected_dates"] is None
    assert not r["market_holidays_or_weekends_inferred"]
    assert not r["independent_bist_second_source_verified"]
    assert not r["licensed_non_display_market_data_access_verified"]
    assert not r["long_term_reliability_proven"]
    assert not r["prices_executable"]
    assert r["orders"] == r["paper_fills"] == r["journal_writes"] == 0
    json.dumps(r, allow_nan=False)


def test_two_distinct_dates_are_multi_date_indicative_only():
    r = summarize_continuity([sample("2026-11-19"), sample("2026-11-20")])
    assert r["status"] == "MULTI_DATE_INDICATIVE_OBSERVATIONS"
    assert r["distinct_observation_dates"] == 2
    assert all(d["complete_indicative_source_coverage"] for d in r["daily_evidence"])
    assert r["long_term_reliability_proven"] is False
    assert r["strategy_profitability_inferred"] is False
    assert r["prices_executable"] is False


def test_explicit_missing_day_reported_not_filled_or_assumed_trading_day():
    r = summarize_continuity(
        [sample("2026-11-19"), sample("2026-11-20")],
        expected_dates=["2026-11-18", "2026-11-19", "2026-11-20"],
    )
    assert r["status"] == "PARTIAL_OR_INTERRUPTED"
    assert r["missing_expected_dates"] == ["2026-11-18"]
    assert "expected_observation_missing_2026-11-18" in r["issues"]
    assert r["market_holidays_or_weekends_inferred"] is False
    assert all(d["date"] != "2026-11-18" for d in r["daily_evidence"])


def test_weekend_not_invented_as_missing_without_explicit_instruction():
    r = summarize_continuity([sample("2026-11-20"), sample("2026-11-23")])
    assert r["status"] == "MULTI_DATE_INDICATIVE_OBSERVATIONS"
    assert r["missing_expected_dates"] is None
    assert r["expected_dates_source"] == "not_specified"
    assert len(r["daily_evidence"]) == 2


def test_partial_or_missing_provider_counts_fail_closed():
    early = sample("2026-11-19")
    late = sample("2026-11-20")
    late["market_daily"]["checks"][0]["price"] = None
    late["official_tcmb"]["checks"][2]["try_per_unit"] = float("nan")
    result = summarize_continuity([early, late])
    assert result["status"] == "PARTIAL_OR_INTERRUPTED"
    day = result["daily_evidence"][1]
    assert day["sources"]["bist100"]["status"] == "missing_or_unverified"
    assert day["sources"]["CNY"]["status"] == "missing_or_unverified"
    assert "bist100_missing_2026-11-20" in result["issues"]
    assert "CNY_missing_2026-11-20" in result["issues"]
    json.dumps(result, allow_nan=False)


def test_single_day_provider_outage_is_intermittent_not_full_coverage():
    first = sample("2026-11-20", hour=10)
    second = sample("2026-11-20", hour=17)
    second["market_daily"]["checks"][2]["status"] = "unavailable_or_unverified"
    second["market_daily"]["checks"][2]["price"] = None
    result = summarize_continuity([first, second])
    assert result["status"] == "INSUFFICIENT_DISTINCT_DATES"
    usd = result["daily_evidence"][0]["sources"]["usdtry"]
    assert usd["status"] == "intermittent_within_day"
    assert usd["observed_count"] == 1
    assert not result["daily_evidence"][0]["complete_indicative_source_coverage"]


def test_source_identity_duplicate_and_future_dates_do_not_qualify():
    r = sample("2026-11-20")
    r["market_daily"]["checks"].append(deepcopy(r["market_daily"]["checks"][0]))
    r["market_daily"]["checks"][1]["source"] = "not_yahoo"
    r["official_tcmb"]["checks"][0]["bulletin_date"] = "2026-11-21"
    out = summarize_continuity([r])
    coverage = out["daily_evidence"][0]["sources"]
    assert coverage["bist100"]["status"] == "missing_or_unverified"
    assert coverage["bist30"]["status"] == "missing_or_unverified"
    assert coverage["USD"]["status"] == "missing_or_unverified"


def test_duplicate_timestamp_cannot_be_double_counted():
    r = sample("2026-11-20")
    with pytest.raises(ValueError, match="duplicate_observation_instant"):
        summarize_continuity([r, deepcopy(r)])


@pytest.mark.parametrize("mutate", [
    lambda r: r.update(orders=1),
    lambda r: r.update(paper_fills=True),
    lambda r: r.update(journal_writes=1),
    lambda r: r.update(live_trading_enabled=True),
    lambda r: r.update(paper_trading_enabled=True),
    lambda r: r.update(scheduler_enabled=True),
    lambda r: r.update(research_only=False),
    lambda r: r.update(prices_executable=True),
    lambda r: r.update(observed_at_istanbul="2026-11-20T12:00:00"),
    lambda r: r.update(observed_at_istanbul="2026-11-21T12:00:00+03:00"),
])
def test_unsafe_or_malformed_report_is_rejected(mutate):
    r = sample("2026-11-20")
    mutate(r)
    with pytest.raises(ValueError):
        summarize_continuity([r])


@pytest.mark.parametrize("dates", [
    [], ["2026-11-20", "2026-11-20"], ["2026-11-19"],
    ["nonsense"], ["2026-11-20T00:00:00"],
])
def test_bad_or_mismatched_expected_dates_refused(dates):
    with pytest.raises(ValueError):
        summarize_continuity([sample("2026-11-20")], expected_dates=dates)


def test_publication_dates_are_not_observation_dates_or_freshness_proof():
    early = sample("2026-11-19")
    late = sample("2026-11-20")
    for row in late["market_daily"]["checks"]:
        row["price_date"] = "2026-11-19"
    for row in late["official_tcmb"]["checks"]:
        row["bulletin_date"] = "2026-11-19"

    result = summarize_continuity([early, late])
    assert result["distinct_observation_dates"] == 2
    assert result["status"] == "MULTI_DATE_REUSED_PUBLICATION_DATES"
    assert not result["provider_publication_days_all_advanced"]
    assert all(e["distinct_publication_dates"] == 1 for e in
               result["provider_publication_evidence"].values())
    assert all(e["progression"] == "same_publication_date_reused" for e in
               result["provider_publication_evidence"].values())
    assert result["daily_evidence"][1]["sources"]["usdtry"]["actual_publication_dates"] == [
        "2026-11-19",
    ]
    assert result["daily_evidence"][1]["sources"]["usdtry"]["max_publication_age_calendar_days"] == 1
    assert "bist100_same_publication_date_on_distinct_observation_days" in result["issues"]
    assert not result["long_term_reliability_proven"]
    assert not result["prices_executable"]


def test_source_publication_backdating_is_reported_even_if_both_observations_exist():
    early = sample("2026-11-20")
    late = sample("2026-11-21")
    late["market_daily"]["checks"][0]["price_date"] = "2026-11-19"
    out = summarize_continuity([early, late])
    assert out["status"] == "PUBLICATION_DATE_REGRESSION"
    assert out["provider_publication_evidence"]["bist100"]["progression"] == "publication_date_regressed"
    assert out["provider_publication_evidence"]["bist30"]["progression"] == "publication_dates_advanced"
    assert "bist100_publication_date_regressed" in out["issues"]
    assert not out["provider_publication_days_all_advanced"]


def test_three_days_with_one_reused_publication_day_remain_unverified():
    rows = [sample(d) for d in ("2026-11-20", "2026-11-21", "2026-11-23")]
    for row in rows[1]["market_daily"]["checks"]:
        row["price_date"] = "2026-11-20"
    for row in rows[1]["official_tcmb"]["checks"]:
        row["bulletin_date"] = "2026-11-20"
    out = summarize_continuity(rows)
    assert out["status"] == "MULTI_DATE_REUSED_PUBLICATION_DATES"
    assert all(e["progression"] == "partially_reused_publication_date"
               for e in out["provider_publication_evidence"].values())
    assert out["market_holidays_or_weekends_inferred"] is False
    assert out["calendar_days_not_equivalent_to_market_sessions"]


def test_marked_no_valid_quotes_cannot_smuggle_positive_prices_into_coverage():
    bad = sample("2026-11-20")
    bad["status"] = "NO_VALID_PROVIDER_QUOTES"
    out = summarize_continuity([bad])
    assert out["status"] == "INSUFFICIENT_DISTINCT_DATES"
    assert all(not d["complete_indicative_source_coverage"] for d in out["daily_evidence"])
    assert all(e["distinct_publication_dates"] == 0 for e in
               out["provider_publication_evidence"].values())
    assert len(out["issues"]) == 7


def test_single_day_with_multiple_publication_dates_still_counts_as_one_day():
    first = sample("2026-11-20", hour=11)
    second = sample("2026-11-20", hour=17)
    first["official_tcmb"]["checks"][0]["bulletin_date"] = "2026-11-19"
    out = summarize_continuity([first, second])
    assert out["status"] == "INSUFFICIENT_DISTINCT_DATES"
    assert out["distinct_observation_dates"] == 1
    assert out["provider_publication_evidence"]["USD"]["distinct_publication_dates"] == 2
    assert out["provider_publication_evidence"]["USD"]["progression"] == "insufficient_observation_dates"
    assert out["daily_evidence"][0]["sources"]["USD"]["actual_publication_dates"] == [
        "2026-11-19", "2026-11-20",
    ]


def test_source_lag_report_retains_real_dates_without_inventing_latest_quote():
    first = sample("2026-11-18")
    later = sample("2026-11-20")
    later["market_daily"]["checks"][3]["price_date"] = "2026-11-18"
    later["official_tcmb"]["checks"][2]["bulletin_date"] = "2026-11-18"
    out = summarize_continuity([first, later])
    assert out["status"] == "MULTI_DATE_REUSED_PUBLICATION_DATES"
    assert out["provider_publication_evidence"]["eurtry"]["actual_publication_dates"] == [
        "2026-11-18",
    ]
    assert out["daily_evidence"][1]["sources"]["eurtry"]["max_publication_age_calendar_days"] == 2
    assert out["daily_evidence"][1]["sources"]["CNY"]["max_publication_age_calendar_days"] == 2
    assert out["provider_publication_evidence"]["bist100"]["distinct_publication_dates"] == 2
    assert not out["provider_publication_days_all_advanced"]


def test_no_observations_or_too_many_is_blocked():
    with pytest.raises(ValueError, match="observation_count_out_of_bounds"):
        summarize_continuity([])
    with pytest.raises(ValueError, match="observation_count_out_of_bounds"):
        summarize_continuity([sample("2026-11-20")] * 31)
