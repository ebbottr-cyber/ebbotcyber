"""Local SQLite MTM recovery: restart invariance and atomic failure contracts."""
from __future__ import annotations

import json
import sqlite3
from copy import deepcopy
from unittest.mock import patch

import pytest

from src.services import meme_coin_paper_recovery as recovery
from src.services.meme_coin_paper_mtm import replay_marked_guarded

MINT = "11111111111111111111111111111111"


def item(event_id, *, at=1000200, amount="100", output="100",
         price="1", stop=False, side="buy"):
    entry = {
        "id": event_id,
        "strategy": "new_launch", "mint": MINT, "side": side,
        "source": "offline_fixture",
        "quote_observed_at_ms": at - 200,
        "attempted_at_ms": at,
        "amount_in": amount, "expected_out": output,
        "network_fee_usd": "0.00", "priority_fee_usd": "0.00",
        "modeled_adverse_slippage_bps": 0, "outcome": "success",
    }
    step = {
        "event": entry,
        "risk_fact": {
            "source": "offline_assumption", "liquidity_usd": "60000",
            "observed_at_ms": at - 100,
        },
        "marks": {MINT: {
            "source": "offline_assumption",
            "bid_price_usd": price, "observed_at_ms": at - 100,
        }},
    }
    if stop:
        step["emergency_stop"] = True
    return step


def test_checkpoint_restore_equal_to_clean_deterministic_replay(tmp_path):
    db = tmp_path / "mtm.sqlite"
    events = [
        item("buy"),
        item("drop", at=1001200, amount="25", price="0.4"),
        item("later", at=1002200, amount="25", price="0.4"),
    ]
    first = recovery.append_and_checkpoint(db, [events[0]])
    assert first["events_inserted"] == 1
    assert first["replay_report"]["ledgers"]["new_launch"]["successful_buys"] == 1
    second = recovery.append_and_checkpoint(db, events[1:])
    assert second["events_restored"] == 3
    assert second["events_inserted"] == 2
    recovered = recovery.verify_and_recover(db)
    assert recovered["replay_report"] == replay_marked_guarded(events)
    assert recovered["replay_report"]["ledgers"]["new_launch"]["daily_mark_drawdown_circuit_open"] is True
    assert recovered["replay_report"]["ledgers"]["new_launch"]["audit"][-1]["reason"] == "daily_strategy_mark_drawdown_limit"
    assert recovered["recovery_used_market_network"] is False
    assert recovered["live_trading_enabled"] is False
    assert recovered["checkpoint_provenance_authenticated"] is False


def test_identical_append_is_idempotent_and_conflicting_same_id_fails(tmp_path):
    db = tmp_path / "offline.sqlite"
    one = item("a")
    recovery.append_and_checkpoint(db, [one])
    retry = recovery.append_and_checkpoint(db, [deepcopy(one)])
    assert retry["events_inserted"] == 0
    assert retry["identical_retries_skipped"] == 1
    altered = deepcopy(one)
    altered["marks"][MINT]["bid_price_usd"] = "0.9"
    with pytest.raises(ValueError, match="conflicting_mtm_event_id"):
        recovery.append_and_checkpoint(db, [altered])
    assert recovery.verify_and_recover(db)["events_restored"] == 1


def test_emergency_stop_latch_survives_restart(tmp_path):
    db = tmp_path / "stop.sqlite"
    original = [item("a"), item("s", at=1001200, amount="25", stop=True)]
    recovery.append_and_checkpoint(db, original)
    later = item("later", at=1002200, amount="25")
    new = recovery.append_and_checkpoint(db, [later])
    a = new["replay_report"]["ledgers"]["new_launch"]
    assert new["replay_report"]["emergency_stop_persisted_in_steps"] is True
    assert [row["reason"] for row in a["audit"]][-2:] == ["emergency_stop", "emergency_stop"]
    assert a["successful_buys"] == 1


def test_interrupted_replay_rolls_back_all_new_steps_and_checkpoint(tmp_path):
    db = tmp_path / "atomic.sqlite"
    recovery.append_and_checkpoint(db, [item("first")])
    original = recovery.replay_marked_guarded

    def failing_replay(steps, **kwargs):
        if len(steps) > 1:
            raise RuntimeError("simulated process failure")
        return original(steps, **kwargs)

    with patch.object(recovery, "replay_marked_guarded", side_effect=failing_replay):
        with pytest.raises(RuntimeError, match="simulated"):
            recovery.append_and_checkpoint(db, [item("next", at=1001200, amount="25")])
    report = recovery.verify_and_recover(db)
    assert report["events_restored"] == 1
    assert report["replay_report"]["ledgers"]["new_launch"]["successful_buys"] == 1


def test_tampered_checkpoint_detected_even_if_hash_updated_to_match(tmp_path):
    db = tmp_path / "corrupt.sqlite"
    recovery.append_and_checkpoint(db, [item("buy")])
    with sqlite3.connect(db) as conn:
        forged = json.dumps({"fake_balance": "2000000"})
        conn.execute(
            "UPDATE mtm_checkpoint SET state_json=?,state_sha256=? WHERE singleton=1",
            (forged, recovery._digest(forged)),
        )
    with pytest.raises(ValueError, match="mtm_checkpoint_integrity_mismatch"):
        recovery.verify_and_recover(db)


def test_tampered_history_detected_without_touching_checkpoint(tmp_path):
    db = tmp_path / "history.sqlite"
    recovery.append_and_checkpoint(db, [item("buy")])
    with sqlite3.connect(db) as conn:
        conn.execute("DROP TRIGGER no_step_update")
        conn.execute("UPDATE mtm_steps SET step_json=? WHERE seq=1", ('{"fake":true}',))
    with pytest.raises(ValueError, match="broken_mtm_event_chain"):
        recovery.verify_and_recover(db)


def test_regular_update_delete_blocked_by_sqlite_triggers(tmp_path):
    db = tmp_path / "blocked.sqlite"
    recovery.append_and_checkpoint(db, [item("a")])
    with sqlite3.connect(db) as conn:
        with pytest.raises(sqlite3.DatabaseError, match="immutable_mtm_history"):
            conn.execute("UPDATE mtm_steps SET event_id='wrong' WHERE seq=1")
        with pytest.raises(sqlite3.DatabaseError, match="immutable_mtm_history"):
            conn.execute("DELETE FROM mtm_steps WHERE seq=1")
    assert recovery.verify_and_recover(db)["events_restored"] == 1


def test_batch_with_bad_second_event_never_commits_first(tmp_path):
    db = tmp_path / "batch.sqlite"
    recovery.append_and_checkpoint(db, [item("prior")])
    good = item("new", at=1001200, amount="25")
    bad = item("invalid", at=1002200, amount="25")
    bad["marks"][MINT]["bid_price_usd"] = "NaN"
    with pytest.raises(ValueError):
        recovery.append_and_checkpoint(db, [good, bad])
    assert recovery.verify_and_recover(db)["events_restored"] == 1


def test_initial_cash_immutable_after_database_creation(tmp_path):
    db = tmp_path / "cash.sqlite"
    recovery.append_and_checkpoint(db, [item("a")], initial_cash_usd="500.00")
    with pytest.raises(ValueError, match="changed_initial_cash"):
        recovery.append_and_checkpoint(
            db, [item("b", at=1001200, amount="25")],
            initial_cash_usd="1000.00",
        )
    assert recovery.verify_and_recover(db)["initial_cash_usd"] == "500.00"


def test_restart_rejects_old_or_out_of_order_event_without_partial_commit(tmp_path):
    db = tmp_path / "order.sqlite"
    recovery.append_and_checkpoint(db, [item("a", at=1001200)])
    with pytest.raises(ValueError, match="nonchronological_mtm_append"):
        recovery.append_and_checkpoint(db, [item("b", at=1000200)])
    assert recovery.verify_and_recover(db)["events_restored"] == 1


def test_missing_checkpoint_is_not_silently_regenerated(tmp_path):
    db = tmp_path / "incomplete.sqlite"
    recovery.append_and_checkpoint(db, [item("a")])
    with sqlite3.connect(db) as conn:
        conn.execute("DELETE FROM mtm_checkpoint")
    with pytest.raises(ValueError, match="missing_mtm_checkpoint"):
        recovery.verify_and_recover(db)


def test_missing_database_is_not_reported_as_empty_success(tmp_path):
    with pytest.raises(ValueError, match="offline_checkpoint_not_found"):
        recovery.verify_and_recover(tmp_path / "missing.sqlite")
