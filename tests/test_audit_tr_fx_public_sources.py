"""Offline-only regression tests for the manual real-provider inspection CLI."""
from __future__ import annotations

from datetime import date, datetime
from io import StringIO
import json
from contextlib import redirect_stdout
from unittest.mock import patch

from scripts import audit_tr_fx_public_sources as audit
from src.services.tr_market_overview_service import INSTRUMENTS, SOURCE


TODAY = date(2026, 11, 20)
NOW = datetime(2026, 11, 20, 18, 0, tzinfo=audit.ISTANBUL)


def _market_rows():
    return {"items": [
        {
            "key": key,
            "label": label,
            "symbol": symbol,
            "currency": currency,
            "status": "ready",
            "source": SOURCE,
            "as_of": "2026-11-19",
            "price": 120.5,
        }
        for key, label, symbol, currency in INSTRUMENTS
    ]}


def _bulletin():
    return {
        "source": "TCMB",
        "rate_kind": "indicative_forex_selling",
        "as_of_date": "2026-11-19",
        "quotes": [{
            "source": "TCMB",
            "source_currency": code,
            "target_currency": "TRY",
            "source_unit": 1,
            "try_per_unit": 20.5,
            "as_of_date": "2026-11-19",
        } for code in audit.EXPECTED_FX],
    }


def test_opt_in_is_required_before_any_network_or_provider_call():
    with patch.object(audit, "build_overview", side_effect=AssertionError("network attempted")), \
         patch.object(audit, "get_tcmb_try_display_quotes", side_effect=AssertionError("network attempted")):
        output = StringIO()
        with redirect_stdout(output):
            assert audit.run() == 0
        result = json.loads(output.getvalue())
    assert result["status"] == "DISABLED"
    assert result["network_requests"] == 0
    assert result["orders"] == 0


def test_good_indicative_bars_and_tcmb_are_still_not_tradable():
    report = audit.summarize(_market_rows(), _bulletin(), today=TODAY, observed_at=NOW)
    assert report["status"] == "READ_ONLY_OBSERVATION"
    assert report["market_daily"]["verified_delayed_quotes"] == 4
    assert report["official_tcmb"]["verified_indicative_rates"] == 3
    assert report["full_observation_coverage"]
    assert report["prices_executable"] is False
    assert report["paper_trading_enabled"] is False
    assert report["live_trading_enabled"] is False
    assert report["unverified_gram_gold"]
    assert report["orders"] == report["paper_fills"] == report["journal_writes"] == 0
    json.dumps(report, allow_nan=False)


def test_invalid_future_old_missing_and_duplicate_quotes_are_not_repaired():
    overview = _market_rows()
    overview["items"][0]["price"] = True
    overview["items"][1]["as_of"] = "2026-11-05"
    overview["items"][2]["as_of"] = "2026-11-21"
    overview["items"][3]["price"] = float("nan")
    result = audit.summarize(overview, _bulletin(), today=TODAY, observed_at=NOW)
    assert result["market_daily"]["verified_delayed_quotes"] == 0
    assert result["market_daily"]["missing_or_unverified"] == 4
    assert all(row["price"] is None and row["price_date"] is None for row in result["market_daily"]["checks"])
    assert result["official_tcmb"]["verified_indicative_rates"] == 3
    json.dumps(result, allow_nan=False)

    overview = _market_rows()
    overview["items"].append(dict(overview["items"][0]))
    result = audit.summarize(overview, _bulletin(), today=TODAY, observed_at=NOW)
    assert result["market_daily"]["verified_delayed_quotes"] == 3
    assert result["market_daily"]["checks"][0]["price"] is None


def test_tcmb_partial_malformed_and_duplicate_rate_rows_fail_closed():
    bulletin = _bulletin()
    bulletin["quotes"][0]["try_per_unit"] = float("inf")
    bulletin["quotes"][1]["source_unit"] = True
    bulletin["quotes"].append(dict(bulletin["quotes"][2]))
    r = audit.summarize(_market_rows(), bulletin, today=TODAY, observed_at=NOW)
    assert r["official_tcmb"]["verified_indicative_rates"] == 0
    assert all(x["try_per_unit"] is None for x in r["official_tcmb"]["checks"])

    bulletin = _bulletin()
    bulletin["as_of_date"] = "2026-11-10"
    r = audit.summarize(_market_rows(), bulletin, today=TODAY, observed_at=NOW)
    assert r["official_tcmb"]["verified_indicative_rates"] == 0
    assert all(x["bulletin_date"] is None for x in r["official_tcmb"]["checks"])


def test_unavailable_network_does_not_become_success_or_fill_quotes():
    buffer = StringIO()
    with patch.object(audit, "build_overview", side_effect=TimeoutError("yahoo unreachable")), \
         patch.object(audit, "get_tcmb_try_display_quotes", side_effect=OSError("tcmb unreachable")), \
         redirect_stdout(buffer):
        assert audit.run(fetch=True) == 0
    result = json.loads(buffer.getvalue())
    assert result["status"] == "NO_VALID_PROVIDER_QUOTES"
    assert result["market_daily"]["missing_or_unverified"] == 4
    assert result["official_tcmb"]["missing_or_unverified"] == 3
    assert result["orders"] == 0
    assert result["prices_executable"] is False


def test_provider_data_does_not_change_symbols_or_source_identity():
    data = _market_rows()
    data["items"][0]["symbol"] = "XU100.SOMETHING"
    data["items"][1]["source"] = "unverified-provider"
    bulletin = _bulletin()
    bulletin["quotes"][0]["target_currency"] = "USD"
    report = audit.summarize(data, bulletin, today=TODAY, observed_at=NOW)
    assert report["market_daily"]["verified_delayed_quotes"] == 2
    assert report["official_tcmb"]["verified_indicative_rates"] == 2
    assert report["market_daily"]["checks"][0]["symbol"] == "XU100.IS"
    assert report["market_daily"]["checks"][0]["price"] is None
