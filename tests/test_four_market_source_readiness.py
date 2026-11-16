# -*- coding: utf-8 -*-
"""Read-only publisher source-check regression; entirely synthetic source files."""
from datetime import date
from pathlib import Path
from urllib.error import URLError

import pytest

from src.services.four_market_source_readiness import (
    _SOURCES,
    check_source,
    source_readiness,
)
from tests.test_ishares_oef_us100_import import _csv as oef_csv
from tests.test_xetra_t7_de100_import import _csv as xetra_csv
from tests.test_hkex_hk100_import import _xlsx as hkex_xlsx

AS_OF = date(2026, 11, 16)


def _fixture_bytes(tmp_path: Path) -> dict[str, bytes]:
    return {
        "us": oef_csv(tmp_path).read_bytes(),
        "de": xetra_csv(tmp_path).read_bytes(),
        "hk": hkex_xlsx(tmp_path).read_bytes(),
    }


def test_three_real_schema_parsers_accept_synthetic_offline_publisher_shapes(tmp_path):
    samples = _fixture_bytes(tmp_path)
    calls: list[str] = []

    def fetch(market):
        calls.append(market)
        return samples[market]

    report = source_readiness(as_of=AS_OF, get_bytes=fetch)
    assert calls == ["us", "de", "hk"]
    assert report["attempted_markets"] == 3
    assert report["schema_passed_markets"] == 3
    assert report["complete_source_checks"] is True
    assert report["stock_rosters_exported"] == 0
    assert report["yahoo_histories_checked"] == 0
    assert report["broker_orders_sent"] == 0
    assert [m["selected_symbols"] for m in report["markets"]] == [100, 100, 100]
    assert all(len(m["source_sha256"]) == 64 for m in report["markets"])
    # Source readiness must not expose licensed issuer holdings or symbols.
    assert all("symbols" not in m and "positions" not in m for m in report["markets"])
    assert all("HK00001" not in str(m) and "BRK.B" not in str(m) for m in report["markets"])


def test_one_upstream_outage_is_inconclusive_not_three_passing_markets(tmp_path):
    samples = _fixture_bytes(tmp_path)
    def fetch(market):
        if market == "hk":
            raise URLError("publisher unavailable")
        return samples[market]

    report = source_readiness(as_of=AS_OF, get_bytes=fetch)
    assert report["schema_passed_markets"] == 2
    assert report["complete_source_checks"] is False
    assert report["markets"][-1]["selected_symbols"] == 0
    assert report["markets"][-1]["status"] == "unavailable_or_invalid"
    assert report["markets"][-1]["source_sha256"] is None


def test_invalid_source_does_not_backfill_candidate_equities(tmp_path):
    sources = _fixture_bytes(tmp_path)
    def damaged(market):
        return b"not an official source" if market == "hk" else sources[market]

    report = source_readiness(as_of=AS_OF, get_bytes=damaged)
    assert report["schema_passed_markets"] == 2
    assert report["markets"][-1]["selected_symbols"] == 0
    assert report["markets"][-1]["error_type"] == "ValueError"


def test_invalid_publisher_age_fails_closed_and_does_not_expose_data(tmp_path):
    data = _fixture_bytes(tmp_path)
    result = check_source("us", as_of=date(2027, 2, 1),
                          get_bytes=data.__getitem__)
    assert result["status"] == "unavailable_or_invalid"
    assert result["selected_symbols"] == 0
    assert result["source_sha256"] is None
    assert "symbols" not in result


def test_oversized_response_does_not_create_temp_candidate_file(tmp_path):
    huge = b"x" * (_SOURCES["us"]["max_bytes"] + 1)
    result = check_source("us", as_of=AS_OF, get_bytes=lambda _: huge)
    assert result["status"] == "unavailable_or_invalid"
    assert result["selected_symbols"] == 0
    assert result["error_type"] == "ValueError"


def test_only_three_enabled_markets_are_accepted():
    with pytest.raises(ValueError, match="distinct US/DE/HK"):
        source_readiness(as_of=AS_OF, markets=("us", "us"))
    with pytest.raises(ValueError, match="distinct US/DE/HK"):
        source_readiness(as_of=AS_OF, markets=("us", "jp"))
    with pytest.raises(ValueError, match="Unsupported market"):
        check_source("jp", as_of=AS_OF)


def test_issuer_network_source_urls_are_hardcoded_to_three_allowlisted_hosts():
    assert _SOURCES["us"]["hostname"] == "www.ishares.com"
    assert _SOURCES["de"]["hostname"] == "www.cashmarket.deutsche-boerse.com"
    assert _SOURCES["hk"]["hostname"] == "www.hkex.com.hk"
    assert len({v["url"] for v in _SOURCES.values()}) == 3
    assert all(v["url"].startswith("https://" + v["hostname"] + "/")
               for v in _SOURCES.values())
