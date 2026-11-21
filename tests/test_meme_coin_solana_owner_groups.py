"""Offline tests for Solana top-token-account owner grouping (never beneficial ownership)."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.endpoints.meme_coin import router
from src.services import meme_coin_solana_owner_groups as owners

MINT = "So11111111111111111111111111111111111111112"
PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
ADDR1 = "11111111111111111111111111111111"
ADDR2 = MINT
ADDR3 = PROGRAM


def snapshots():
    supply = {"context": {"slot": 4000}, "value": {"amount": "1000", "decimals": 9}}
    largest = {"context": {"slot": 4004}, "value": [
        {"address": ADDR1, "amount": "200"},
        {"address": ADDR2, "amount": "150"},
        {"address": ADDR3, "amount": "50"},
    ]}
    grouped = {"context": {"slot": 4005}, "value": [
        {
            "owner": PROGRAM,
            "data": {
                "program": "spl-token", "parsed": {
                    "type": "account", "info": {"mint": MINT, "owner": ADDR1,
                                              "tokenAmount": {"amount": amount}},
                },
            },
        }
        for amount in ("200", "150", "50")
    ]}
    grouped["value"][2]["data"]["parsed"]["info"]["owner"] = ADDR2
    return supply, largest, grouped


def test_owner_groups_sum_token_account_balances_by_onchain_control_address():
    state = owners.assess_owner_groups(MINT, *snapshots())
    assert state["status"] == "screened"
    assert state["verdict"] == "concentration_signal"
    assert state["observed_top_token_accounts"] == 3
    assert state["observed_owner_groups"] == 2
    assert state["largest_observed_owner_share_pct"] == 35
    assert state["owner_groups"][0] == {
        "owner_address": ADDR1, "sampled_token_accounts": 2,
        "share_of_total_supply_pct": 35.0,
    }
    assert state["beneficial_ownership_verified"] is False
    assert state["vault_classification_verified"] is False
    assert state["tradable"] is False


def test_below_threshold_still_only_review():
    supply, largest, grouped = snapshots()
    supply["value"]["amount"] = "2000"
    state = owners.assess_owner_groups(MINT, supply, largest, grouped)
    assert state["verdict"] == "review_only"
    assert state["largest_observed_owner_share_pct"] == 17.5
    assert state["tradable"] is False


@pytest.mark.parametrize("condition", [
    "wrong_mint", "owner_missing", "amount_mismatch", "missing_account",
    "slot_gap", "unparsed", "unsupported_program", "broken_owner",
])
def test_fail_closed_when_token_account_data_inconsistent(condition):
    supply, largest, grouped = snapshots()
    if condition == "wrong_mint":
        grouped["value"][0]["data"]["parsed"]["info"]["mint"] = ADDR1
    elif condition == "owner_missing":
        grouped["value"][0]["data"]["parsed"]["info"].pop("owner")
    elif condition == "amount_mismatch":
        grouped["value"][0]["data"]["parsed"]["info"]["tokenAmount"]["amount"] = "100"
    elif condition == "missing_account":
        grouped["value"][0] = None
    elif condition == "slot_gap":
        grouped["context"]["slot"] = 5000
    elif condition == "unparsed":
        grouped["value"][0]["data"] = ["base64", "base64"]
    elif condition == "unsupported_program":
        grouped["value"][0]["owner"] = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
    elif condition == "broken_owner":
        grouped["value"][0]["data"]["parsed"]["info"]["owner"] = "nope"
    with pytest.raises((ValueError, TypeError)):
        owners.assess_owner_groups(MINT, supply, largest, grouped)


def test_disabled_by_default_does_not_contact_network():
    owners._CACHE.clear()
    with patch.dict("os.environ", {"MEME_COIN_SOLANA_OWNER_GROUPS_ENABLED": "false"}):
        with patch.object(owners, "_fetch_rpc") as f, patch.object(owners, "fetch_grouped_accounts") as g:
            state = owners.review_owner_groups(MINT)
    f.assert_not_called()
    g.assert_not_called()
    assert state["status"] == "disabled"
    assert state["tradable"] is False


def test_enabled_fetches_three_read_methods_and_uses_cache():
    owners._CACHE.clear()
    supply, largest, grouped = snapshots()
    def respond(method, mint):
        assert mint == MINT
        assert method in {"getTokenSupply", "getTokenLargestAccounts"}
        return supply if method == "getTokenSupply" else largest
    with patch.dict("os.environ", {"MEME_COIN_SOLANA_OWNER_GROUPS_ENABLED": "true"}):
        with patch.object(owners, "_fetch_rpc", side_effect=respond) as fetch, patch.object(owners, "fetch_grouped_accounts", return_value=grouped) as many:
            first = owners.review_owner_groups(MINT)
            first["owner_groups"][0]["owner_address"] = "mutated"
            second = owners.review_owner_groups(MINT)
    assert fetch.call_count == 2
    assert many.call_count == 1
    assert many.call_args.args == ([ADDR1, ADDR2, ADDR3],)
    assert second["owner_groups"][0]["owner_address"] == ADDR1


def test_rpc_failure_is_not_empty_success():
    owners._CACHE.clear()
    with patch.dict("os.environ", {"MEME_COIN_SOLANA_OWNER_GROUPS_ENABLED": "true"}):
        with patch.object(owners, "_fetch_rpc", side_effect=RuntimeError("rate limited")):
            state = owners.review_owner_groups(MINT)
    assert state["status"] == "unavailable"
    assert state["owner_groups"] == []
    assert state["tradable"] is False


def test_api_remains_read_only():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/meme-coins")
    client = TestClient(app)
    with patch.dict("os.environ", {"MEME_COIN_SOLANA_OWNER_GROUPS_ENABLED": "false"}):
        r = client.get("/api/v1/meme-coins/solana/owner-groups", params={"mint": MINT})
    assert r.status_code == 200
    assert r.json()["beneficial_ownership_verified"] is False
    assert r.json()["status"] == "disabled"
    assert client.get("/api/v1/meme-coins/solana/owner-groups", params={"mint": "bad"}).status_code == 422
    assert client.post("/api/v1/meme-coins/solana/owner-groups", json={}).status_code == 405
