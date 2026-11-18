"""No API, wallet, price feed or network. SQLite uses pytest tmp_path only."""
from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest

from src.services.meme_coin_persistent_journal import (
    append_synthetic_scenario, read_synthetic_scenarios,
    latch_synthetic_kill_switch,
)
from src.services.meme_coin_strategy_service import get_meme_coin_overview


def e(key="one", strategy="new_launch", day="2026-11-18", **changes):
    values = {
        "event_id": key, "trading_day": day, "strategy": strategy,
        "synthetic_entry_price_usd": "1", "synthetic_exit_price_usd": "1",
        "requested_notional_usd": "10",
        "synthetic_pool_liquidity_usd": "100000",
        "snapshot_age_seconds": "10",
    }
    values.update(changes)
    return values


def add(path, event, equity="1000"):
    return append_synthetic_scenario(
        database_path=path, starting_equity_usd=equity,
        event=event, enabled=True,
    )


def get(path, equity="1000"):
    return read_synthetic_scenarios(
        database_path=path, starting_equity_usd=equity, enabled=True,
    )


def test_disabled_by_default_is_immutable_and_fileless(tmp_path):
    path = tmp_path / "offline.sqlite3"
    r = append_synthetic_scenario(
        database_path=path, starting_equity_usd="1000", event=e(),
    )
    assert r["reason"] == "offline_storage_disabled"
    assert read_synthetic_scenarios(
        database_path=path, starting_equity_usd="1000",
    )["status"] == "blocked"
    assert not path.exists()


def test_reopen_persists_both_strategies_and_reconciles(tmp_path):
    path = tmp_path / "offline.sqlite3"
    assert add(path, e("n", synthetic_exit_price_usd="1.5"))["append_result"] == "synthetic_recorded"
    assert add(path, e("m", "momentum", synthetic_exit_price_usd="0.5"))["append_result"] == "synthetic_recorded"
    snapshot = get(path)
    assert snapshot["event_count"] == 2
    assert snapshot["strategies"]["new_launch"]["synthetic_round_trips"] == 1
    assert snapshot["strategies"]["momentum"]["synthetic_round_trips"] == 1
    assert snapshot["status"] == "synthetic_storage_snapshot"
    assert snapshot["trade_executed"] is False
    assert snapshot["paper_trading_enabled"] is False
    assert snapshot["realized_performance"] is False
    assert get(path) == snapshot
    assert get(path, equity="1500")["reason"] == "equity_mismatch"
    for item in get_meme_coin_overview()["strategies"]:
        assert item["paper_trading_enabled"] is False
        assert item["metrics"]["trades"] is None


def test_duplicate_is_idempotent_and_conflicting_id_fails_closed(tmp_path):
    path = tmp_path / "offline.sqlite3"
    first = e("same")
    result = add(path, first)
    digest = result["audit_tip_sha256"]
    assert add(path, first)["append_result"] == "duplicate_ignored"
    assert add(path, e("same", strategy="momentum"))["reason"] == "conflicting_event_id"
    assert get(path)["event_count"] == 1
    assert get(path)["audit_tip_sha256"] == digest


def test_loss_budget_enforced_across_restart_and_next_day(tmp_path):
    path = tmp_path / "offline.sqlite3"
    assert add(path, e("loss1", synthetic_exit_price_usd="0.01",
                       requested_notional_usd="20"))["append_result"] == "synthetic_recorded"
    assert add(path, e("loss2", "momentum",
                       synthetic_exit_price_usd="0.01",
                       requested_notional_usd="19"))["append_result"] == "synthetic_recorded"
    assert add(path, e("other", "momentum"))["reason"] == "global_daily_risk_budget"
    assert get(path)["event_count"] == 2
    assert add(path, e("next", "momentum", day="2026-11-19"))["append_result"] == "synthetic_recorded"
    assert get(path)["event_count"] == 3


def test_kill_switch_is_sticky_after_reopening(tmp_path):
    path = tmp_path / "offline.sqlite3"
    assert add(path, e())["append_result"] == "synthetic_recorded"
    assert latch_synthetic_kill_switch(
        database_path=path, starting_equity_usd="1000", enabled=True,
    )["reason"] == "manual_kill_switch"
    assert get(path)["kill_switch_latched"] is True
    assert add(path, e("later", day="2026-11-19"))["reason"] == "manual_kill_switch"
    assert get(path)["event_count"] == 1


def test_tampered_payload_detected_without_partial_write(tmp_path):
    path = tmp_path / "offline.sqlite3"
    assert add(path, e())["append_result"] == "synthetic_recorded"
    with sqlite3.connect(path) as db:
        db.execute("UPDATE synthetic_scenarios SET payload=? WHERE event_id='one'",
                   ('{"event_id":"forged"}',))
    assert get(path)["reason"] == "journal_integrity_failed"
    assert add(path, e("two"))["reason"] == "journal_integrity_failed"


def test_invalid_input_never_creates_or_changes_event_count(tmp_path):
    path = tmp_path / "offline.sqlite3"
    assert add(path, e("bad", synthetic_entry_price_usd="NaN"))["status"] == "blocked"
    assert not path.exists() or get(path)["event_count"] == 0
    assert add(path, e("valid"))["append_result"] == "synthetic_recorded"
    assert add(path, {**e("extra"), "token_address": "nope"})["status"] == "blocked"
    assert get(path)["event_count"] == 1


def test_out_of_order_days_are_rejected(tmp_path):
    path = tmp_path / "offline.sqlite3"
    assert add(path, e("later", day="2026-11-19"))["append_result"] == "synthetic_recorded"
    assert add(path, e("earlier", day="2026-11-18"))["reason"] == "events_out_of_order"
    assert get(path)["event_count"] == 1


def test_two_simultaneous_appenders_do_not_overwrite(tmp_path):
    path = tmp_path / "offline.sqlite3"
    # Initialise schema before starting concurrent transactions.
    assert add(path, e("initial"))["append_result"] == "synthetic_recorded"
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(add, path, e("worker" + str(i),
                                          strategy="momentum")) for i in range(2)]
        results = [f.result() for f in futures]
    assert all(result["append_result"] == "synthetic_recorded" for result in results)
    assert get(path)["event_count"] == 3


def test_persistent_layer_never_calls_network_and_no_default_file(tmp_path):
    path = tmp_path / "offline.sqlite3"
    with patch("urllib.request.urlopen", side_effect=AssertionError("network forbidden")):
        assert add(path, e())["append_result"] == "synthetic_recorded"
        assert get(path)["event_count"] == 1
    assert not (tmp_path / "other.sqlite3").exists()


@pytest.mark.parametrize("value", [False, None, 0, "yes"])
def test_opt_in_must_be_exact_boolean_true(tmp_path, value):
    path = tmp_path / "offline.sqlite3"
    assert append_synthetic_scenario(
        database_path=path, starting_equity_usd="1000",
        event=e(), enabled=value,
    )["reason"] == "offline_storage_disabled"
    assert not path.exists()
