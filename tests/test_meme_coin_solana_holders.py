"""Offline tests for opt-in Solana token-account concentration (not wallet owners)."""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.endpoints.meme_coin import router
from src.services import meme_coin_solana_holders as holders

MINT = "So11111111111111111111111111111111111111112"
ACCOUNTS = [
    "11111111111111111111111111111111",
    "So11111111111111111111111111111111111111112",
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
]


def snapshots(amounts=(200, 150, 50), *, supply=1000, slot=10000, account_slot=10015):
    supply_snapshot = {
        "context": {"slot": slot},
        "value": {"amount": str(supply), "decimals": 6, "uiAmountString": "0.001"},
    }
    account_snapshot = {
        "context": {"slot": account_slot},
        "value": [
            {"address": address, "amount": str(amount), "decimals": 6}
            for address, amount in zip(ACCOUNTS, amounts)
        ],
    }
    return supply_snapshot, account_snapshot


def test_concentration_is_a_warning_and_never_trading_permission():
    supply, accounts = snapshots()
    result = holders.assess_concentration(MINT, supply, accounts)
    assert result["status"] == "screened"
    assert result["verdict"] == "concentration_signal"
    assert result["top_account_pct"] == 20
    assert result["top_ten_accounts_pct"] == 40
    assert result["warning_flags"] == ["top_token_account_at_least_20pct"]
    assert result["interpretation"] == "token_accounts_not_wallets"
    assert result["owner_identity_verified"] is False
    assert result["pool_vaults_classified"] is False
    assert result["full_safety_verified"] is False
    assert result["tradable"] is False


def test_low_concentration_also_never_means_safe():
    supply, accounts = snapshots(amounts=(50, 30, 20))
    result = holders.assess_concentration(MINT, supply, accounts)
    assert result["status"] == "screened"
    assert result["verdict"] == "review_only"
    assert result["warning_flags"] == []
    assert result["top_ten_accounts_pct"] == 10
    assert result["tradable"] is False


def test_top_ten_concentration_flag_independent_of_top_account_flag():
    supply, accounts = snapshots(amounts=(190, 185, 185), supply=750)
    result = holders.assess_concentration(MINT, supply, accounts)
    assert result["top_account_pct"] > 20  # both flags, no safety conclusion
    assert "top_ten_token_accounts_at_least_70pct" in result["warning_flags"]


@pytest.mark.parametrize("alter", [
    "slot_mismatch", "larger_than_supply", "duplicate", "unsorted",
    "bad_address", "empty_accounts", "zero_supply", "bad_supply",
    "invalid_decimals",
])
def test_incomplete_or_inconsistent_snapshots_fail_closed(alter):
    supply, accounts = snapshots()
    if alter == "slot_mismatch":
        accounts["context"]["slot"] = 12000
    elif alter == "larger_than_supply":
        accounts["value"][0]["amount"] = "9999"
    elif alter == "duplicate":
        accounts["value"][1]["address"] = accounts["value"][0]["address"]
    elif alter == "unsorted":
        accounts["value"][0]["amount"] = "1"
    elif alter == "bad_address":
        accounts["value"][0]["address"] = "https://example.com"
    elif alter == "empty_accounts":
        accounts["value"] = []
    elif alter == "zero_supply":
        supply["value"]["amount"] = "0"
    elif alter == "bad_supply":
        supply["value"]["amount"] = "NaN"
    elif alter == "invalid_decimals":
        supply["value"]["decimals"] = True
    with pytest.raises(ValueError):
        holders.assess_concentration(MINT, supply, accounts)


def test_disabled_default_does_not_call_network():
    with patch.dict("os.environ", {"MEME_COIN_SOLANA_HOLDER_AUDIT_ENABLED": "false"}):
        with patch.object(holders, "_fetch_rpc") as fetch:
            result = holders.review_concentration(MINT)
    fetch.assert_not_called()
    assert result["status"] == "disabled"
    assert result["top_account_pct"] is None
    assert result["tradable"] is False


def test_enabled_uses_only_two_read_methods_and_caches():
    holders._CACHE.clear()
    supply, accounts = snapshots()
    def fake_rpc(method, mint):
        assert mint == MINT
        return supply if method == "getTokenSupply" else accounts
    with patch.dict("os.environ", {"MEME_COIN_SOLANA_HOLDER_AUDIT_ENABLED": "true"}):
        with patch.object(holders, "_fetch_rpc", side_effect=fake_rpc) as fetch:
            a = holders.review_concentration(MINT)
            a["warning_flags"].clear()
            b = holders.review_concentration(MINT)
    assert fetch.call_count == 2
    assert [c.args[0] for c in fetch.call_args_list] == ["getTokenSupply", "getTokenLargestAccounts"]
    assert b["warning_flags"] == ["top_token_account_at_least_20pct"]


def test_provider_failure_is_unavailable_not_silent_green():
    holders._CACHE.clear()
    with patch.dict("os.environ", {"MEME_COIN_SOLANA_HOLDER_AUDIT_ENABLED": "true"}):
        with patch.object(holders, "_fetch_rpc", side_effect=RuntimeError("rate limited")):
            result = holders.review_concentration(MINT)
    assert result["status"] == "unavailable"
    assert result["verdict"] == "unknown"
    assert result["tradable"] is False


def test_json_rpc_only_allows_read_methods():
    with pytest.raises(ValueError):
        holders._fetch_rpc("sendTransaction", MINT)
    with pytest.raises(ValueError):
        holders._fetch_rpc("getTokenLargestAccounts", "invalid")


def test_authenticated_route_contract_never_enables_trading():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/meme-coins")
    client = TestClient(app)
    with patch.dict("os.environ", {"MEME_COIN_SOLANA_HOLDER_AUDIT_ENABLED": "false"}):
        response = client.get("/api/v1/meme-coins/solana/concentration", params={"mint": MINT})
    assert response.status_code == 200
    body = response.json()
    assert body["interpretation"] == "token_accounts_not_wallets"
    assert body["status"] == "disabled"
    assert body["tradable"] is False
    assert client.post("/api/v1/meme-coins/solana/concentration", json={}).status_code == 405
    assert client.get("/api/v1/meme-coins/solana/concentration", params={"mint": "bad"}).status_code == 422
