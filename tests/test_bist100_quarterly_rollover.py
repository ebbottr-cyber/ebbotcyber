# -*- coding: utf-8 -*-
"""Offline quarterly-roster contract: never pretend to know the 2027 members.

Q1 below is a deliberately synthetic test fixture in pytest's temporary
directory, NOT a real/approved BIST100 member list. No new roster is shipped.
"""
from copy import deepcopy
from datetime import date
import json
import sys

import pytest

from src.services import bist100_universe as universe


DAY = date(2027, 1, 4)
KNOWN = date(2026, 11, 15)


def _old_candidate():
    return json.loads(universe._SNAPSHOT_PATH.read_text(encoding="utf-8"))


def _synthetic_reviewed_q1(monkeypatch, tmp_path):
    data = tmp_path / "rosters"
    data.mkdir()
    original = _old_candidate()
    (data / "bist100_constituents_2026q4.json").write_text(
        json.dumps(original), encoding="utf-8"
    )
    # Invented test fixture ONLY. BALSU was not active in old Q4;
    # remove AEFES so the fabricated set still has exactly 100 tickers.
    candidate = deepcopy(original)
    candidate.update({
        "effective_from": "2027-01-01",
        "effective_to": "2027-03-31",
        "as_of": "2027-01-04",
        "verified_on": "2027-01-05",
        "provenance": "SYNTHETIC TEST DATA ONLY — NOT REAL 2027 BIST100 MEMBERS",
        "constituents": sorted((set(original["constituents"]) - {"AEFES.IS"}) | {"BALSU.IS"}),
        "official_additions": ["BALSU.IS"],
        "official_exclusions": ["AEFES.IS"],
        "official_substitutes": [],
        "sources": {
            "official_periodic_changes": "https://example.invalid/synthetic-q1",
            "full_roster": "https://example.invalid/synthetic-roster",
            "independent_roster": "https://example.invalid/synthetic-crosscheck",
        },
    })
    target = data / "bist100_constituents_2027q1.json"
    target.write_text(json.dumps(candidate), encoding="utf-8")
    monkeypatch.setattr(universe, "_SNAPSHOT_DIRECTORY", data)
    return data, target, candidate


def test_actual_2026_q4_roster_remains_stable_and_can_end_on_dec31():
    roster = universe.load_bist100_universe(date(2026, 12, 31))
    assert len(roster.symbols) == 100
    assert roster.effective_from == date(2026, 10, 1)
    assert roster.effective_to == date(2026, 12, 31)
    assert len(roster.additions) == 27
    assert len(roster.exclusions) == 27
    assert len(roster.substitutes) == 3


@pytest.mark.parametrize("when", [
    date(2027, 1, 1), date(2027, 1, 4), date(2027, 3, 31),
    date(2027, 4, 1),
])
def test_missing_new_quarter_never_reuses_stale_previous_constituents(when):
    with pytest.raises(ValueError, match="not valid.*reviewed"):
        universe.load_bist100_universe(when)


def test_2027_cli_is_blocked_and_does_not_claim_a_new_real_roster(monkeypatch, capsys):
    monkeypatch.setattr(
        sys, "argv", ["bist100_universe", "--for-date", "2027-01-04"]
    )
    with pytest.raises(SystemExit) as exit_info:
        universe.main()
    assert exit_info.value.code == 2
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "blocked_missing_or_invalid_roster"
    assert output["required_snapshot"] == "bist100_constituents_2027q1.json"
    assert "Do not reuse" in output["disclaimer"]


def test_simulated_q1_requires_exact_prior_roster_deltas(monkeypatch, tmp_path):
    _synthetic_reviewed_q1(monkeypatch, tmp_path)
    roster = universe.load_bist100_universe(DAY)
    assert roster.effective_from == date(2027, 1, 1)
    assert len(roster.symbols) == 100
    assert "BALSU.IS" in roster.symbols
    assert "AEFES.IS" not in roster.symbols
    assert roster.additions == ("BALSU.IS",)
    assert roster.exclusions == ("AEFES.IS",)


def test_simulated_2027_q1_preflight_is_structural_only(monkeypatch, tmp_path, capsys):
    _synthetic_reviewed_q1(monkeypatch, tmp_path)
    monkeypatch.setattr(
        sys, "argv", ["bist100_universe", "--for-date", "2027-01-04"]
    )
    universe.main()
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "structurally_valid_not_live_verified"
    assert output["constituents"] == 100
    assert output["changes_in"] == output["changes_out"] == 1


def test_old_roster_cannot_pass_with_falsely_claimed_new_additions(monkeypatch, tmp_path):
    _, target, payload = _synthetic_reviewed_q1(monkeypatch, tmp_path)
    payload["constituents"] = _old_candidate()["constituents"]
    target.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="official additions are missing"):
        universe.load_bist100_universe(DAY)


def test_mismatched_official_change_lists_cannot_pass(monkeypatch, tmp_path):
    _, target, payload = _synthetic_reviewed_q1(monkeypatch, tmp_path)
    payload["official_additions"] = ["BINHO.IS"]
    target.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="actual prior roster changes"):
        universe.load_bist100_universe(DAY)


def test_reusing_2026_official_notice_is_rejected(monkeypatch, tmp_path):
    _, target, payload = _synthetic_reviewed_q1(monkeypatch, tmp_path)
    payload["sources"]["official_periodic_changes"] = _old_candidate()["sources"][
        "official_periodic_changes"
    ]
    target.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="reuses previous official announcement"):
        universe.load_bist100_universe(DAY)


def test_truncated_or_overlapping_quarter_is_rejected(monkeypatch, tmp_path):
    _, target, payload = _synthetic_reviewed_q1(monkeypatch, tmp_path)
    payload["effective_to"] = "2027-02-28"
    target.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="exactly one quarter"):
        universe.load_bist100_universe(DAY)


def test_missing_preceding_quarter_rejects_even_full_100(monkeypatch, tmp_path):
    data, _, _ = _synthetic_reviewed_q1(monkeypatch, tmp_path)
    (data / "bist100_constituents_2026q4.json").unlink()
    with pytest.raises(ValueError, match="not valid"):
        universe.load_bist100_universe(DAY)


def test_symlink_to_unreviewed_roster_file_is_not_followed(monkeypatch, tmp_path):
    _, target, _ = _synthetic_reviewed_q1(monkeypatch, tmp_path)
    new_location = tmp_path / "redirected.json"
    target.rename(new_location)
    target.symlink_to(new_location)
    with pytest.raises(ValueError, match="not valid"):
        universe.load_bist100_universe(DAY)


def test_2027_q1_candidate_cannot_claim_q2_dates(monkeypatch, tmp_path):
    _, target, payload = _synthetic_reviewed_q1(monkeypatch, tmp_path)
    payload["effective_from"] = "2027-04-01"
    payload["effective_to"] = "2027-06-30"
    payload["as_of"] = "2027-04-02"
    payload["verified_on"] = "2027-04-02"
    target.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="not valid"):
        universe.load_bist100_universe(DAY)


def test_invalid_extra_symbols_never_pass_future_synthetic_roster(monkeypatch, tmp_path):
    _, target, payload = _synthetic_reviewed_q1(monkeypatch, tmp_path)
    payload["constituents"].append("XU100.IS")
    target.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="canonical"):
        universe.load_bist100_universe(DAY)
