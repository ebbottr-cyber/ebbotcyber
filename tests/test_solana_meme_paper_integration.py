"""Use real Meme Radar watch/blocked logic to drive the offline paper ledger."""
import json
from pathlib import Path

import pytest

from scripts.solana_meme_paper_replay import run_fixture

BASE = Path(__file__).parent / "fixtures"


def read(name):
    return json.loads((BASE / name).read_text(encoding="utf-8"))


def test_synthetic_upward_path_trades_both_strategies():
    out = run_fixture(read("solana_paper_synthetic_up.json"))
    assert out["data_origin"] == "synthetic"
    assert out["trading_enabled"] is False
    assert out["external_network_requests"] == 0
    for name in ("new_coin_hunter", "momentum_watcher"):
        x = out["strategies"][name]
        assert x["entries"] == 1
        assert len(x["closed_trades"]) == 1
        assert x["closed_trades"][0]["exit_fill_ms"] > x["closed_trades"][0]["exit_signal_ms"]


def test_synthetic_downward_gap_is_a_loss_not_guaranteed_stop():
    out = run_fixture(read("solana_paper_synthetic_down.json"))
    for strategy in ("new_coin_hunter", "momentum_watcher"):
        x = out["strategies"][strategy]
        assert x["entries"] == 1
        assert float(x["closed_trades"][0]["pnl_usd"]) < -8


def test_missing_goplus_risk_flags_block_all_entries():
    doc = read("solana_paper_synthetic_up.json")
    for row in doc["snapshots"]:
        row["security"] = None
    out = run_fixture(doc)
    assert all(x["entries"] == 0 for x in out["strategies"].values())


def test_new_hunter_rejects_dex_screener_profile_feed():
    doc = read("solana_paper_synthetic_up.json")
    for row in doc["snapshots"]:
        row["source"] = "dexscreener"
    out = run_fixture(doc)
    assert out["strategies"]["new_coin_hunter"]["entries"] == 0
    assert out["strategies"]["momentum_watcher"]["entries"] == 1


def test_invalid_origin_or_nonchronological_fixture_fails_closed():
    doc = read("solana_paper_synthetic_up.json")
    doc["data_origin"] = "live_verified"
    with pytest.raises(ValueError):
        run_fixture(doc)
    doc["data_origin"] = "synthetic"
    doc["snapshots"][1]["timestamp_ms"] = doc["snapshots"][0]["timestamp_ms"]
    with pytest.raises(ValueError):
        run_fixture(doc)
