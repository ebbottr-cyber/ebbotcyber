# -*- coding: utf-8 -*-
"""Offline tests for the source-checked 2026-Q4 BIST100 membership snapshot."""
from datetime import date
import json

import pytest

from src.services.bist100_universe import (
    _SNAPSHOT_PATH,
    is_bist100_member,
    load_bist100_universe,
    validate_bist100_snapshot,
)
from src.services.bist_symbols import normalize_bist_equity_symbol


OFFICIAL_ADDITIONS = set((
    "AGHOL AHGAZ AKCNS AKFYE ALBRK ANHYT AYGAZ BINHO ECZYT EGEEN "
    "EGGUB ENTRA GLYHO GWIND ISDMR KARSN KATMR KCAER KORDS LMKDC "
    "RGYAS RYSAS SNGYO TABGD TCKRC TRGYO TTRAK"
).split())
OFFICIAL_EXCLUSIONS = set((
    "BALSU BSOKE DAPGM DSTKF EFOR ESEN EUPWR GENIL GESAN GRTHO GSRAY "
    "IEYHO IZENR KLRHO KTLEV KUYAS MAGEN MIATK ODINE PASEU PATEK "
    "PSGYO QUAGR RALYH REEDR SARKY SKBNK"
).split())
OFFICIAL_SUBSTITUTES = {"KLGYO", "RYGYO", "TMSN"}


def _source_payload():
    return json.loads(_SNAPSHOT_PATH.read_text(encoding="utf-8"))


def test_bist100_universe_is_exactly_100_canonical_yahoo_stocks():
    universe = load_bist100_universe(date(2026, 11, 15))
    assert len(universe.symbols) == len(set(universe.symbols)) == 100
    assert list(universe.symbols) == sorted(universe.symbols)
    assert all(normalize_bist_equity_symbol(s) == s for s in universe.symbols)
    assert "XU100.IS" not in universe.symbols
    assert universe.effective_from == date(2026, 10, 1)
    assert universe.effective_to == date(2026, 12, 31)
    assert universe.as_of == date(2026, 11, 8)
    assert universe.verified_on == date(2026, 11, 15)
    assert len(universe.source_urls) == 3
    assert is_bist100_member("thyao.is", date(2026, 11, 15))
    assert is_bist100_member("AKFYE.IS", date(2026, 11, 15))
    assert not is_bist100_member("AAPL", date(2026, 11, 15))
    assert not is_bist100_member("XU100.IS", date(2026, 11, 15))


def test_bist100_official_changes_match_full_roster_not_substitutes():
    universe = load_bist100_universe(date(2026, 11, 8))
    to_bare = lambda seq: {x.removesuffix(".IS") for x in seq}
    assert to_bare(universe.additions) == OFFICIAL_ADDITIONS
    assert to_bare(universe.exclusions) == OFFICIAL_EXCLUSIONS
    assert to_bare(universe.substitutes) == OFFICIAL_SUBSTITUTES
    assert set(universe.additions).issubset(universe.symbols)
    assert not (set(universe.exclusions) | set(universe.substitutes)) & set(universe.symbols)


@pytest.mark.parametrize("when", [date(2026, 9, 30), date(2027, 1, 1)])
def test_bist100_universe_fails_closed_outside_effective_period(when):
    with pytest.raises(ValueError, match="not valid"):
        load_bist100_universe(when)


@pytest.mark.parametrize("field,mutator,expected", [
    ("constituents", lambda p: p["constituents"].append("ZZZZZ.IS"), "exactly 100"),
    ("constituents", lambda p: p["constituents"].__setitem__(0, "AKBNK.IS"), "duplicate"),
    ("constituents", lambda p: p["constituents"].__setitem__(0, "XU100.IS"), "canonical"),
    ("official_exclusions", lambda p: p["official_exclusions"].append("THYAO.IS"), "active members"),
    ("official_substitutes", lambda p: p["official_substitutes"].append("ASELS.IS"), "active members"),
    ("currency", lambda p: p.__setitem__("currency", "CNY"), "metadata"),
    ("effective_to", lambda p: p.__setitem__("effective_to", "2026-09-30"), "dates"),
    ("sources", lambda p: p["sources"].pop("independent_roster"), "source provenance"),
])
def test_bist100_snapshot_rejects_invalid_or_stale_data(field, mutator, expected):
    payload = _source_payload()
    mutator(payload)
    with pytest.raises(ValueError, match=expected):
        validate_bist100_snapshot(payload)
