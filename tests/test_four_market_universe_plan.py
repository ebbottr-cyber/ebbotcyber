# -*- coding: utf-8 -*-
"""Offline checks: BIST100 is a sourced roster; foreign inputs are not invented."""
from copy import deepcopy
from datetime import date
import json

import pytest

from src.services.four_market_universe_plan import (
    _load_foreign_roster,
    create_universe_plan,
)


AS_OF = date(2026, 11, 16)
SOURCES = {
    "us": "https://www.spglobal.com/spdji/en/indices/equity/sp-100/",
    "de": "https://www.stoxx.com/index-details?symbol=DAX",
    "hk": "https://www.hsi.com.hk/en-hk/indexes/all-indexes/index-details/?seriesCode=hsci",
}


def _codes(market):
    # Purely synthetic contract fixtures, NOT live stock symbols or memberships.
    if market == "us":
        return ["U" + chr(65 + n // 26) + chr(65 + n % 26) for n in range(100)]
    if market == "de":
        return [f"D{n:04d}.DE" for n in range(100)]
    if market == "hk":
        return [f"HK{n + 1:05d}" for n in range(100)]
    raise AssertionError("unknown fixture market")


def _snapshot(market):
    return {
        "market": market,
        "as_of": "2026-11-16",
        "source_name": "Operator review required; fixture only",
        "source_url": SOURCES[market],
        "symbols": _codes(market),
    }


def _write_rosters(tmp_path):
    paths = {}
    for market in ("us", "de", "hk"):
        target = tmp_path / (market + ".json")
        target.write_text(json.dumps(_snapshot(market)), encoding="utf-8")
        paths[market] = target
    return paths


def test_default_has_real_bist100_members_but_never_implies_400_complete():
    report = create_universe_plan(as_of=AS_OF)
    assert report["scope"] == "etre_four_market_source_dated_universe_plan"
    assert report["target_symbols_total"] == 400
    assert report["prepared_symbols"] == 100
    assert report["remaining_symbols"] == 300
    assert report["markets"]["tr"]["count"] == 100
    assert "borsaistanbul.com" in report["markets"]["tr"]["source_url"]
    assert report["markets"]["us"]["status"] == "source_roster_missing"
    assert report["markets"]["de"]["status"] == "source_roster_missing"
    assert report["markets"]["hk"]["status"] == "source_roster_missing"
    assert report["missing_markets"] == ["us", "de", "hk"]
    assert "symbols" not in report
    assert report["complete"] is False


def test_complete_four_market_contract_accepts_only_100_each(tmp_path):
    report = create_universe_plan(as_of=AS_OF, source_paths=_write_rosters(tmp_path))
    assert report["complete"] is True
    assert report["prepared_symbols"] == 400
    assert report["remaining_symbols"] == 0
    assert len(report["symbols"]) == 400
    assert len(set(report["symbols"])) == 400
    assert report["symbols"][0].endswith(".IS")
    assert report["symbols"][100].startswith("U")
    assert report["symbols"][200].endswith(".DE")
    assert report["symbols"][300].startswith("HK")
    assert [report["markets"][market]["count"] for market in
            ("tr", "us", "de", "hk")] == [100, 100, 100, 100]


@pytest.mark.parametrize("market,modify", [
    ("us", lambda x: x.update(as_of="2026-06-01")),
    ("us", lambda x: x.update(as_of="2026-11-30")),
    ("us", lambda x: x.update(market="jp")),
    ("de", lambda x: x.update(source_url="http://localhost:8000/roster")),
    ("de", lambda x: x.update(symbols=x["symbols"][:-1])),
    ("hk", lambda x: x["symbols"].append(x["symbols"][0])),
    ("hk", lambda x: x["symbols"].__setitem__(0, "7203.T")),
])
def test_invalid_foreign_source_fails_without_export(tmp_path, market, modify):
    paths = _write_rosters(tmp_path)
    bad = json.loads(paths[market].read_text(encoding="utf-8"))
    modify(bad)
    paths[market].write_text(json.dumps(bad), encoding="utf-8")
    report = create_universe_plan(as_of=AS_OF, source_paths=paths)
    assert report["complete"] is False
    assert report["markets"][market]["count"] == 0
    assert "symbols" not in report
    assert market in report["missing_markets"]


def test_rejects_unknown_roster_type_and_bist100_snapshot_outside_quarter(tmp_path):
    paths = _write_rosters(tmp_path)
    with pytest.raises(ValueError, match="Unexpected market"):
        create_universe_plan(as_of=AS_OF, source_paths={**paths, "jp": paths["hk"]})
    with pytest.raises(ValueError, match="not valid"):
        create_universe_plan(as_of=date(2027, 1, 1), source_paths=paths)


def test_rejects_non_https_and_oversized_foreign_roster(tmp_path):
    path = tmp_path / "us.json"
    candidate = _snapshot("us")
    candidate["source_url"] = "http://www.spglobal.com/indices"
    path.write_text(json.dumps(candidate), encoding="utf-8")
    with pytest.raises(ValueError, match="HTTPS"):
        _load_foreign_roster("us", path, as_of=AS_OF)
    path.write_bytes(b" " * 100001)
    with pytest.raises(ValueError, match="100 KB"):
        _load_foreign_roster("us", path, as_of=AS_OF)
