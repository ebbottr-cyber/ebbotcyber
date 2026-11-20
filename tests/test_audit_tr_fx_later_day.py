"""Offline-only later-day authorization and price-publication truth regressions."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from scripts.audit_tr_fx_later_day import (
    MIN_FOLLOWUP_DATE, compare_later_observation, fetch_gate, run,
)
from src.services.tr_market_overview_service import SOURCE as YAHOO_SOURCE

TZ = __import__("zoneinfo").ZoneInfo("Europe/Istanbul")


def when(day: str, hh: int = 12, minute: int = 0) -> datetime:
    return datetime.fromisoformat(f"{day}T{hh:02d}:{minute:02d}:00+03:00")


def observation(day: str, *, publication_day: str | None = None, hour: int = 12):
    published = publication_day or day
    return {
        "status": "READ_ONLY_OBSERVATION",
        "observed_at_istanbul": when(day, hour).isoformat(),
        "as_of_local_date": day,
        "research_only": True,
        "prices_executable": False,
        "paper_trading_enabled": False,
        "live_trading_enabled": False,
        "scheduler_enabled": False,
        "orders": 0,
        "paper_fills": 0,
        "journal_writes": 0,
        "market_daily": {"checks": [
            {
                "key": key, "symbol": symbol, "currency": "TRY",
                "label": key, "source": YAHOO_SOURCE,
                "price": 100.0, "price_date": published,
                "status": "observed_delayed_daily",
                "indicative_only": True, "executable_quote": False,
            }
            for key, symbol in (
                ("bist100", "XU100.IS"),
                ("bist30", "XU030.IS"),
                ("usdtry", "TRY=X"),
                ("eurtry", "EURTRY=X"),
            )
        ]},
        "official_tcmb": {"checks": [
            {
                "currency": currency, "target_currency": "TRY",
                "try_per_unit": 50.0, "bulletin_date": published,
                "source": "TCMB daily ForexSelling",
                "status": "observed_official_indicative", "executable_quote": False,
            }
            for currency in ("USD", "EUR", "CNY")
        ]},
    }


BASELINE = observation("2026-11-20")


@pytest.mark.parametrize("day", [
    "2026-11-20", "2026-11-21", "2026-11-22",
])
def test_friday_and_weekend_never_allow_public_get(day):
    with patch("src.services.tr_market_overview_service.build_overview",
               side_effect=AssertionError("public GET attempted")), \
         patch("src.services.tcmb_try_display_service.get_tcmb_try_display_quotes",
               side_effect=AssertionError("public GET attempted")):
        result = run(BASELINE, now=when(day), fetch=True)
    assert result["status"] == "NOT_ELIGIBLE_YET"
    assert result["public_quote_requests_allowed"] is False
    assert result["network_requests"] == 0
    assert result["orders"] == result["paper_fills"] == 0


def test_monday_is_only_eligible_for_manual_observation_not_market_session():
    assert MIN_FOLLOWUP_DATE.isoformat() == "2026-11-23"
    ready = fetch_gate(BASELINE, when("2026-11-23"))
    assert ready["status"] == "ELIGIBLE_LATER_WEEKDAY"
    assert ready["public_quote_requests_allowed"] is True
    assert ready["market_open_verified"] is False
    assert ready["market_holidays_inferred"] is False
    assert ready["user_opt_in_required"] is True


def test_eligible_but_without_fetch_is_network_free():
    with patch("src.services.tr_market_overview_service.build_overview",
               side_effect=AssertionError("GET attempted")), \
         patch("src.services.tcmb_try_display_service.get_tcmb_try_display_quotes",
               side_effect=AssertionError("GET attempted")):
        result = run(BASELINE, now=when("2026-11-23"), fetch=False)
    assert result["status"] == "READY_FOR_MANUAL_PUBLIC_DATA_READ"
    assert result["network_requests"] == 0


def test_later_day_and_new_publication_dates_still_only_indicative():
    result = compare_later_observation(
        deepcopy(BASELINE), observation("2026-11-23"), now=when("2026-11-23"),
    )
    assert result["status"] == "MULTI_DATE_INDICATIVE_OBSERVATIONS"
    assert result["distinct_observation_dates"] == 2
    assert result["all_provider_publication_dates_advanced"] is True
    assert result["new_source_day_proven_for_every_source"] is True
    assert all(row["distinct_publication_dates"] == 2
               for row in result["per_source_publication_evidence"].values())
    assert not result["market_open_verified"]
    assert not result["long_term_reliability_proven"]
    assert not result["independent_bist_second_source_verified"]
    assert not result["prices_executable"]
    assert result["orders"] == result["paper_fills"] == result["journal_writes"] == 0


def test_later_day_replays_friday_publication_and_cannot_be_called_fresh():
    followup = observation("2026-11-23", publication_day="2026-11-20")
    result = compare_later_observation(BASELINE, followup, now=when("2026-11-23"))
    assert result["status"] == "MULTI_DATE_REUSED_PUBLICATION_DATES"
    assert not result["all_provider_publication_dates_advanced"]
    assert not result["new_source_day_proven_for_every_source"]
    for row in result["per_source_publication_evidence"].values():
        assert row["progression"] == "same_publication_date_reused"
        assert row["actual_publication_dates"] == ["2026-11-20"]
    assert not result["prices_executable"]


def test_partial_provider_outage_does_not_substitute_other_source():
    followup = observation("2026-11-23")
    followup["market_daily"]["checks"][0]["price"] = None
    followup["market_daily"]["checks"][3]["price_date"] = "2026-11-20"
    followup["official_tcmb"]["checks"][0]["try_per_unit"] = float("nan")
    result = compare_later_observation(BASELINE, followup, now=when("2026-11-23"))
    assert result["status"] == "PARTIAL_OR_INTERRUPTED"
    assert result["per_source_publication_evidence"]["bist100"]["progression"] == "incomplete_source_days"
    assert result["per_source_publication_evidence"]["USD"]["progression"] == "incomplete_source_days"
    assert result["per_source_publication_evidence"]["eurtry"]["progression"] == "same_publication_date_reused"
    assert not result["new_source_day_proven_for_every_source"]
    assert result["orders"] == 0


@pytest.mark.parametrize("mutate", [
    lambda r: r.update(as_of_local_date="2026-11-20"),
    lambda r: r.update(observed_at_istanbul="2026-11-24T12:00:00+03:00"),
    lambda r: r.update(observed_at_istanbul="2026-11-23T11:40:00+03:00"),
    lambda r: r.update(observed_at_istanbul="2026-11-20T12:00:00+03:00"),
])
def test_replayed_or_wrong_clock_followup_is_refused(mutate):
    future = observation("2026-11-23")
    mutate(future)
    with pytest.raises(ValueError):
        compare_later_observation(BASELINE, future, now=when("2026-11-23"))


def test_fake_second_day_must_not_be_loaded_on_initial_weekend():
    future = observation("2026-11-23")
    with pytest.raises(ValueError, match="not_a_later_eligible_weekday"):
        compare_later_observation(BASELINE, future, now=when("2026-11-22"))


def test_timezone_naive_clock_refused_before_any_fetch():
    with pytest.raises(ValueError, match="actual_timezone_aware_clock_required"):
        fetch_gate(BASELINE, datetime(2026, 11, 23, 12, 0))


def test_monday_mock_source_failure_returns_explicit_partial_not_success():
    with patch("src.services.tr_market_overview_service.build_overview",
               side_effect=OSError("offline")), \
         patch("src.services.tcmb_try_display_service.get_tcmb_try_display_quotes",
               side_effect=OSError("offline")):
        # summarize_current uses the supplied Istanbul test clock. All fields
        # are unavailable: no guessed price and no fake second-source corroboration.
        result = run(BASELINE, now=when("2026-11-23"), fetch=True)
    assert result["status"] == "PARTIAL_OR_INTERRUPTED"
    assert not result["all_provider_publication_dates_advanced"]
    assert not result["new_source_day_proven_for_every_source"]
    assert all(row["progression"] == "incomplete_source_days"
               for row in result["per_source_publication_evidence"].values())
    assert not result["prices_executable"]
