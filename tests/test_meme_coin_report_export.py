"""Offline export uses an explicit local SQLite path; no network/wallet."""
from __future__ import annotations

import json
import sqlite3

from src.services.meme_coin_persistent_journal import append_synthetic_scenario
from src.services.meme_coin_report_export import FORMAT, export_synthetic_report


def _event():
    return {
        "event_id": "syn-1", "trading_day": "2026-11-18",
        "strategy": "new_launch", "synthetic_entry_price_usd": "1",
        "synthetic_exit_price_usd": "1.2", "requested_notional_usd": "10",
        "synthetic_pool_liquidity_usd": "100000", "snapshot_age_seconds": "10",
    }


def _init(tmp_path):
    db = tmp_path / "research.sqlite3"
    assert append_synthetic_scenario(
        database_path=db, starting_equity_usd="1000",
        event=_event(), enabled=True,
    )["status"] == "synthetic_storage_snapshot"
    return db


def test_export_disabled_by_default_and_no_output_created(tmp_path):
    database = _init(tmp_path)
    destination = tmp_path / "report.json"
    result = export_synthetic_report(
        database_path=database, starting_equity_usd="1000",
        output_path=destination,
    )
    assert result["reason"] == "offline_export_disabled"
    assert not destination.exists()


def test_export_contains_only_explicitly_labeled_synthetic_records(tmp_path):
    database = _init(tmp_path)
    destination = tmp_path / "report.json"
    result = export_synthetic_report(
        database_path=database, starting_equity_usd="1000",
        output_path=destination, enabled=True,
    )
    assert result["status"] == "exported"
    raw = json.loads(destination.read_text("utf-8"))
    assert set(raw) == {"format", "snapshot"}
    assert raw["format"] == FORMAT
    report = raw["snapshot"]
    assert report["event_count"] == 1
    assert report["strategies"]["new_launch"]["synthetic_round_trips"] == 1
    assert report["strategies"]["momentum"]["synthetic_round_trips"] == 0
    assert report["trade_executed"] is False
    assert report["paper_trading_enabled"] is False
    assert report["live_trading_enabled"] is False
    assert report["realized_performance"] is False
    assert "token_address" not in destination.read_text("utf-8")
    assert "api_key" not in destination.read_text("utf-8")
    assert result["event_count"] == 1


def test_export_refuses_overwrite_and_unrelated_extension(tmp_path):
    database = _init(tmp_path)
    destination = tmp_path / "report.json"
    destination.write_text("existing")
    result = export_synthetic_report(
        database_path=database, starting_equity_usd="1000",
        output_path=destination, enabled=True,
    )
    assert result["reason"] == "output_already_exists"
    assert destination.read_text() == "existing"
    result = export_synthetic_report(
        database_path=database, starting_equity_usd="1000",
        output_path=tmp_path / "report.sqlite3", enabled=True,
    )
    assert result["reason"] == "invalid_output_path"


def test_tampered_journal_and_wrong_equity_do_not_export(tmp_path):
    database = _init(tmp_path)
    destination = tmp_path / "report.json"
    wrong = export_synthetic_report(
        database_path=database, starting_equity_usd="999",
        output_path=destination, enabled=True,
    )
    assert wrong["reason"] == "equity_mismatch"
    assert not destination.exists()
    with sqlite3.connect(database) as conn:
        conn.execute("UPDATE synthetic_scenarios SET payload='{}'")
    corrupted = export_synthetic_report(
        database_path=database, starting_equity_usd="1000",
        output_path=destination, enabled=True,
    )
    assert corrupted["reason"] == "journal_integrity_failed"
    assert not destination.exists()

def test_cli_requires_explicit_synthetic_acknowledgement(tmp_path, capsys):
    from scripts.export_meme_coin_synthetic_report import main

    database = _init(tmp_path)
    destination = tmp_path / "report.json"
    flags = ["--database", str(database), "--equity", "1000",
             "--output", str(destination)]
    assert main(flags) == 1
    assert not destination.exists()
    assert main(flags + ["--confirm-synthetic-only"]) == 0
    assert destination.exists()
    assert json.loads(destination.read_text("utf-8"))["format"] == FORMAT
