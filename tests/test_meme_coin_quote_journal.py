"""Offline SQLite quote journal integrity, atomicity, and isolation tests."""
from __future__ import annotations

import json
import sqlite3
from copy import deepcopy

import pytest

from src.services.meme_coin_jupiter_quotes import USDC_MINT, normalize_quote
from src.services.meme_coin_quote_journal import append_captures, verify_journal

MINT = "11111111111111111111111111111111"


def quote(strategy="new_launch", *, timestamp=1000000, output="100000000"):
    request = {
        "strategy": strategy, "mint": MINT, "side": "buy",
        "source": "jupiter_swap_v2_order_quote_only",
        "input_mint": USDC_MINT, "output_mint": MINT,
        "amount_in_raw": "25000000",
    }
    provider = {
        "inAmount": "25000000", "outAmount": output,
        "router": "metis", "feeBps": 2, "transaction": None,
    }
    return normalize_quote(request, provider, observed_at_ms=timestamp)


def test_separate_hash_chains_survive_reopen_and_idempotent_import(tmp_path):
    db = tmp_path / "private-quotes.sqlite"
    first = quote()
    second = quote("momentum")
    result = append_captures(db, [first, second])
    assert result["inserted"] == 2
    assert result["strategy_counts"] == {"new_launch": 1, "momentum": 1}
    assert result["provenance_authenticated"] is False
    assert result["append_only_against_privileged_attackers"] is False
    assert result["live_trading_enabled"] is False
    assert result["chain_tips"]["new_launch"] != result["chain_tips"]["momentum"]

    rerun = append_captures(db, [first, second])
    assert rerun["inserted"] == 0
    assert rerun["duplicate_identical_skipped"] == 2
    assert verify_journal(db)["strategy_counts"] == {"new_launch": 1, "momentum": 1}

    append_captures(db, [quote(timestamp=2000000, output="90000000")])
    assert verify_journal(db)["strategy_counts"] == {"new_launch": 2, "momentum": 1}


def test_bad_capture_hash_rejected_without_creating_archive(tmp_path):
    db = tmp_path / "quotes.sqlite"
    bad = deepcopy(quote())
    bad["amount_out_raw"] = "999"
    with pytest.raises(ValueError, match="integrity"):
        append_captures(db, [bad])
    assert not db.exists()


@pytest.mark.parametrize("change", [
    lambda q: q.update({"transaction_returned": True}),
    lambda q: q.update({"tradable": True}),
    lambda q: q.update({"execution_is_real": True}),
    lambda q: q.update({"strategy": "robinhood_chain"}),
    lambda q: q.update({"captured_at": "unknown"}),
    lambda q: q.update({"private_key": "never"}),
])
def test_unsafe_or_incompatible_quotes_never_enter_archive(tmp_path, change):
    item = quote()
    change(item)
    with pytest.raises((ValueError, TypeError)):
        append_captures(tmp_path / "quotes.sqlite", [item])


def test_append_batch_is_atomic_if_later_entry_invalid(tmp_path):
    db = tmp_path / "quotes.sqlite"
    initial = quote(timestamp=1000000)
    append_captures(db, [initial])
    with pytest.raises(ValueError, match="nonchronological"):
        append_captures(db, [
            quote(timestamp=3000000, output="50000000"),
            quote(timestamp=2000000, output="40000000"),
        ])
    assert verify_journal(db)["strategy_counts"]["new_launch"] == 1


def test_db_triggers_reject_regular_edit_and_delete(tmp_path):
    db = tmp_path / "quotes.sqlite"
    append_captures(db, [quote()])
    with sqlite3.connect(db) as conn:
        with pytest.raises(sqlite3.DatabaseError, match="immutable_quote_journal"):
            conn.execute("UPDATE quote_journal SET entry_hash=? WHERE strategy=?",
                         ("bad", "new_launch"))
        with pytest.raises(sqlite3.DatabaseError, match="immutable_quote_journal"):
            conn.execute("DELETE FROM quote_journal WHERE strategy=?", ("new_launch",))
    assert verify_journal(db)["strategy_counts"]["new_launch"] == 1


def test_chained_hash_rejects_privileged_sql_tampering(tmp_path):
    db = tmp_path / "quotes.sqlite"
    append_captures(db, [quote(), quote(timestamp=2000000, output="95000000")])
    with sqlite3.connect(db) as conn:
        conn.execute("DROP TRIGGER no_quote_update")
        conn.execute(
            "UPDATE quote_journal SET capture_json=? WHERE strategy=? AND seq=1",
            (json.dumps({"tampered": True}), "new_launch"),
        )
    with pytest.raises(ValueError):
        verify_journal(db)
    with pytest.raises(ValueError):
        append_captures(db, [quote(timestamp=3000000)])


def test_two_strategies_can_have_same_capture_timestamp_but_not_same_capture_id(tmp_path):
    db = tmp_path / "quotes.sqlite"
    a = quote("new_launch", timestamp=1000000)
    b = quote("momentum", timestamp=1000000)
    append_captures(db, [a, b])
    assert verify_journal(db)["strategy_counts"] == {"new_launch": 1, "momentum": 1}
    with pytest.raises(ValueError, match="nonchronological"):
        append_captures(db, [quote("momentum", timestamp=999999, output="777")])


def test_cli_like_archive_snapshot_contains_no_wallet_or_performance(tmp_path):
    info = append_captures(tmp_path / "local.sqlite", [quote()])
    exported = json.dumps(info)
    assert "wallet" not in exported.lower()
    assert "profit" not in exported.lower()
    assert "realized" not in exported.lower()
