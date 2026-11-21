"""Offline Orca Whirlpool layout and on-chain vault verification contracts."""
from __future__ import annotations

import base64
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.endpoints.meme_coin import router
from src.services import meme_coin_solana_orca as orca

POOL = "11111111111111111111111111111111"
MINT_A = "So11111111111111111111111111111111111111112"
MINT_B = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
VAULT_A = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
VAULT_B = "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc"


def key_bytes(address: str) -> bytes:
    value = 0
    for char in address:
        value = value * 58 + orca._ALPHABET.index(char)
    raw = value.to_bytes(32, "big")
    assert orca.base58_encode(raw) == address
    return raw


def snapshots(*, amount_a="420000", amount_b="120000", liquidity=123456,
              pool_slot=1000, vault_slot=1004):
    data = bytearray(653)
    data[0:8] = orca.WHIRLPOOL_DISCRIMINATOR
    data[49:65] = liquidity.to_bytes(16, "little")
    data[65:81] = (1 << 64).to_bytes(16, "little")
    data[101:133] = key_bytes(MINT_A)
    data[133:165] = key_bytes(VAULT_A)
    data[181:213] = key_bytes(MINT_B)
    data[213:245] = key_bytes(VAULT_B)

    pool = {"context": {"slot": pool_slot}, "value": {
        "owner": orca.WHIRLPOOL_PROGRAM, "executable": False,
        "data": [base64.b64encode(data).decode("ascii"), "base64"],
        "lamports": 2000000, "space": 653,
    }}

    def vault(mint: str, amount: str):
        return {
            "owner": orca.CLASSIC_SPL_TOKEN_PROGRAM,
            "data": {"program": "spl-token", "parsed": {
                "type": "account", "info": {
                    "mint": mint, "owner": POOL, "state": "initialized",
                    "tokenAmount": {"amount": amount, "decimals": 6},
                },
            }},
        }

    vaults = {"context": {"slot": vault_slot}, "value": [
        vault(MINT_A, amount_a), vault(MINT_B, amount_b),
    ]}
    return pool, vaults


def test_official_layout_offsets_and_vaults_inspect_only():
    pool, vaults = snapshots()
    state = orca.inspect_orca(MINT_A, POOL, pool, vaults)
    assert state["status"] == "screened"
    assert state["verdict"] == "review_only"
    assert state["pool_program"] == orca.WHIRLPOOL_PROGRAM
    assert state["mint_a"] == MINT_A and state["mint_b"] == MINT_B
    assert state["vault_a"] == VAULT_A and state["vault_b"] == VAULT_B
    assert state["vault_a_raw_amount"] == "420000"
    assert state["vault_b_raw_amount"] == "120000"
    assert state["clmm_liquidity_raw"] == "123456"
    assert state["vault_authority_matches_pool"] is True
    assert state["vault_reserves_observed"] is True
    for guard in ("active_swap_depth_verified", "liquidity_lock_verified",
                  "lp_withdrawal_authority_verified", "sellability_verified", "tradable"):
        assert state[guard] is False


def test_zero_vault_or_liquidity_flags_and_never_trades():
    pool, vaults = snapshots(amount_a="0", liquidity=0)
    result = orca.inspect_orca(MINT_A, POOL, pool, vaults)
    assert result["verdict"] == "blocked"
    assert "empty_pool_vault" in result["warnings"]
    assert "zero_current_clmm_liquidity" in result["warnings"]
    assert result["tradable"] is False


@pytest.mark.parametrize("alter", [
    "different_mint", "stale_slot", "wrong_vault_mint",
    "wrong_vault_authority", "delegated_vault", "bad_vault_program",
    "pool_discriminator", "invalid_pool_size", "empty_sqrt_price",
    "missing_vault", "unparsed_vault", "wrong_pool_program",
])
def test_bad_accounts_fail_closed(alter):
    pool, vaults = snapshots()
    mint = MINT_A
    if alter == "different_mint":
        mint = VAULT_B
    elif alter == "stale_slot":
        vaults["context"]["slot"] = 2000
    elif alter == "wrong_vault_mint":
        vaults["value"][0]["data"]["parsed"]["info"]["mint"] = MINT_B
    elif alter == "wrong_vault_authority":
        vaults["value"][1]["data"]["parsed"]["info"]["owner"] = MINT_A
    elif alter == "delegated_vault":
        vaults["value"][0]["data"]["parsed"]["info"]["delegate"] = MINT_B
    elif alter == "bad_vault_program":
        vaults["value"][0]["owner"] = MINT_B
    elif alter in {"pool_discriminator", "invalid_pool_size", "empty_sqrt_price"}:
        data = bytearray(base64.b64decode(pool["value"]["data"][0]))
        if alter == "pool_discriminator":
            data[0:8] = b"NOTORCAA"
        elif alter == "invalid_pool_size":
            data = data[:-1]
        else:
            data[65:81] = bytes(16)
        pool["value"]["data"][0] = base64.b64encode(data).decode()
    elif alter == "missing_vault":
        vaults["value"][0] = None
    elif alter == "unparsed_vault":
        vaults["value"][0]["data"] = ["AA==", "base64"]
    elif alter == "wrong_pool_program":
        pool["value"]["owner"] = MINT_B

    with pytest.raises((ValueError, TypeError)):
        orca.inspect_orca(mint, POOL, pool, vaults)


def test_disabled_audit_never_calls_solana_rpc():
    orca._CACHE.clear()
    with patch.dict("os.environ", {"MEME_COIN_ORCA_VAULT_AUDIT_ENABLED": "false"}):
        with patch.object(orca, "_rpc") as fetch:
            state = orca.review_orca_vaults(MINT_A, POOL)
        fetch.assert_not_called()
    assert state["status"] == "disabled"
    assert state["vault_reserves_observed"] is False


def test_non_orca_dex_skips_vault_requests_and_reports_unsupported():
    orca._CACHE.clear()
    pool, _ = snapshots()
    pool["value"]["owner"] = MINT_B
    with patch.dict("os.environ", {"MEME_COIN_ORCA_VAULT_AUDIT_ENABLED": "true"}):
        with patch.object(orca, "_rpc", return_value=pool) as rpc:
            state = orca.review_orca_vaults(MINT_A, POOL)
    assert state["status"] == "unsupported"
    assert state["tradable"] is False
    assert rpc.call_count == 1


def test_enabled_makes_two_read_calls_then_caches_without_leaking_mutations():
    orca._CACHE.clear()
    pool, vaults = snapshots()
    with patch.dict("os.environ", {"MEME_COIN_ORCA_VAULT_AUDIT_ENABLED": "true"}):
        with patch.object(orca, "_rpc", side_effect=[pool, vaults]) as fetch:
            first = orca.review_orca_vaults(MINT_A, POOL)
            first["warnings"].append("bad_mutation")
            second = orca.review_orca_vaults(MINT_A, POOL)
    assert fetch.call_count == 2
    assert fetch.call_args_list[0].args == ("getAccountInfo", [POOL], "base64")
    assert fetch.call_args_list[1].args == ("getMultipleAccounts", [VAULT_A, VAULT_B], "jsonParsed")
    assert second["status"] == "screened"
    assert second["warnings"] == []


def test_rpc_failure_does_not_produce_fake_balance_or_success():
    orca._CACHE.clear()
    with patch.dict("os.environ", {"MEME_COIN_ORCA_VAULT_AUDIT_ENABLED": "true"}):
        with patch.object(orca, "_rpc", side_effect=RuntimeError("timeout")):
            state = orca.review_orca_vaults(MINT_A, POOL)
    assert state["status"] == "unavailable"
    assert state["vault_a_raw_amount"] is None
    assert state["tradable"] is False


def test_rpc_rejects_write_methods_and_unapproved_shapes():
    with pytest.raises(ValueError):
        orca._rpc("sendTransaction", [POOL], "base64")
    with pytest.raises(ValueError):
        orca._rpc("getAccountInfo", [POOL], "jsonParsed")
    with pytest.raises(ValueError):
        orca._rpc("getMultipleAccounts", [POOL], "jsonParsed")


def test_read_only_api_contract():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/meme-coins")
    client = TestClient(app)
    with patch.dict("os.environ", {"MEME_COIN_ORCA_VAULT_AUDIT_ENABLED": "false"}):
        response = client.get("/api/v1/meme-coins/solana/orca-vaults", params={
            "mint": MINT_A, "pool": POOL,
        })
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "disabled"
    assert body["tradable"] is False
    assert body["active_swap_depth_verified"] is False
    assert client.get("/api/v1/meme-coins/solana/orca-vaults", params={
        "mint": "bad", "pool": POOL,
    }).status_code == 422
    assert client.post("/api/v1/meme-coins/solana/orca-vaults", json={}).status_code == 405
