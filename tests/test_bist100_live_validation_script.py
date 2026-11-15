# -*- coding: utf-8 -*-
"""Offline safety contract for the operator-invoked Windows real-data smoke.

These tests do not run Yahoo requests or write the user's production database.
They verify the script keeps write consent limited to an isolated SQLite file.
"""
from datetime import date
from pathlib import Path

from src.services.bist100_universe import load_bist100_universe


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "bist100-live-validation.ps1"
FIVE = ("THYAO.IS", "ASELS.IS", "AKBNK.IS", "TUPRS.IS", "AKFYE.IS")


def test_safe_five_member_selection_is_in_the_dated_bist100_universe():
    members = set(load_bist100_universe(date(2026, 11, 15)).symbols)
    assert len(FIVE) == len(set(FIVE)) == 5
    assert set(FIVE).issubset(members)
    script = SCRIPT.read_text(encoding="utf-8")
    assert ",".join(FIVE) in script


def test_script_uses_new_isolated_database_and_restores_environment():
    script = SCRIPT.read_text(encoding="utf-8")
    assert "$originalDb" in script
    assert "$wasSet" in script
    assert "$env:DATABASE_PATH = $stageDatabase" in script
    assert "Remove-Item Env:DATABASE_PATH" in script
    assert "$env:DATABASE_PATH = $originalDb" in script
    assert "[guid]::NewGuid()" in script
    assert "Refusing to overwrite a database" in script
    assert "Push-Location $repository" in script
    assert "Pop-Location" in script
    assert "Test-Path -LiteralPath $stageDatabase" in script


def test_import_is_explicitly_gated_before_five_or_full_ranking():
    script = SCRIPT.read_text(encoding="utf-8")
    assert "Confirm-Import -Report" in script
    assert "Confirm-Ranking -Report" in script
    assert script.index("Confirm-Import -Report") < script.index("Confirm-Ranking -Report")
    assert "'--write-db'" in script
    assert "'--db-path', $stageDatabase" in script
    assert "if ($Full100)" in script
    assert "Full100 explicitly requested" in script
    assert "No live orders" not in script or "trade" in script.lower()


def test_runs_only_from_reviewed_branch_with_2026_q4_snapshot():
    script = SCRIPT.read_text(encoding="utf-8")
    assert "feat/bist100-mvp" in script
    assert "2026-10-01" in script
    assert "2026-12-31" in script
    assert "2026-11-15" in script
    assert "src.services.bist100_import" in script
    assert "src.services.bist100_screener" in script
    assert "Read-StrictJson" in script
