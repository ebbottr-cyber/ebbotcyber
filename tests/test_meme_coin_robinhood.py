"""Offline, read-only Robinhood Chain network probe tests."""
from __future__ import annotations

import json
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.endpoints.meme_coin import router
from src.services import meme_coin_robinhood as robinhood


class FakeResponse:
    def __init__(self, result):
        self.payload = json.dumps({"jsonrpc": "2.0", "id": 1, "result": result}).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, _limit):
        return self.payload


def test_disabled_default_makes_no_external_calls():
    robinhood._CACHE.clear()
    with patch.dict("os.environ", {
        "MEME_COIN_ROBINHOOD_RPC_ENABLED": "false",
        "MEME_COIN_ROBINHOOD_NETWORK": "testnet",
    }):
        with patch.object(robinhood, "urlopen") as network:
            state = robinhood.get_robinhood_rpc_status()
            network.assert_not_called()
    assert state["status"] == "disabled"
    assert state["chain_id_expected"] == 46630
    assert state["trading_enabled"] is False


def test_opt_in_reads_chain_id_and_latest_block_only():
    robinhood._CACHE.clear()
    calls = []

    def get_response(request, timeout=0):
        assert timeout <= 7
        assert request.full_url == "https://rpc.testnet.chain.robinhood.com"
        payload = json.loads(request.data)
        assert payload["params"] == []
        assert payload["method"] in {"eth_chainId", "eth_blockNumber"}
        calls.append(payload["method"])
        return FakeResponse("0xb626" if payload["method"] == "eth_chainId" else "0x1234")

    # 0xb626 == 46630
    with patch.dict("os.environ", {
        "MEME_COIN_ROBINHOOD_RPC_ENABLED": "true",
        "MEME_COIN_ROBINHOOD_NETWORK": "testnet",
    }):
        with patch.object(robinhood, "urlopen", side_effect=get_response):
            state = robinhood.get_robinhood_rpc_status()
    assert state["status"] == "ok"
    assert state["block_number"] == 0x1234
    assert state["chain_id_seen"] == 46630
    assert state["trading_enabled"] is False
    assert calls == ["eth_chainId", "eth_blockNumber"]


def test_wrong_chain_id_never_reads_block_or_enables_trade():
    robinhood._CACHE.clear()
    with patch.dict("os.environ", {
        "MEME_COIN_ROBINHOOD_RPC_ENABLED": "true",
        "MEME_COIN_ROBINHOOD_NETWORK": "mainnet",
    }):
        with patch.object(robinhood, "_rpc", return_value=46630) as method:
            state = robinhood.get_robinhood_rpc_status()
    assert state["status"] == "mismatch"
    assert state["trading_enabled"] is False
    assert state["block_number"] is None
    assert method.call_count == 1


def test_rpc_unavailable_fails_closed():
    robinhood._CACHE.clear()
    with patch.dict("os.environ", {
        "MEME_COIN_ROBINHOOD_RPC_ENABLED": "true",
        "MEME_COIN_ROBINHOOD_NETWORK": "mainnet",
    }):
        with patch.object(robinhood, "_rpc", side_effect=TimeoutError("timeout")):
            state = robinhood.get_robinhood_rpc_status()
    assert state["status"] == "unavailable"
    assert state["chain_id_seen"] is None
    assert state["trading_enabled"] is False


def test_read_only_methods_and_urls_are_strictly_restricted():
    for url, method in [
        ("https://example.com", "eth_chainId"),
        ("https://rpc.mainnet.chain.robinhood.com", "eth_sendRawTransaction"),
    ]:
        try:
            robinhood._rpc(url, method)
        except ValueError:
            pass
        else:
            raise AssertionError("RPC request must reject unsafe endpoints or methods")


def test_api_never_exposes_wallet_or_order_mutation():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/meme-coins")
    client = TestClient(app)

    with patch.dict("os.environ", {"MEME_COIN_ROBINHOOD_RPC_ENABLED": "false"}):
        response = client.get("/api/v1/meme-coins/robinhood/status")
    assert response.status_code == 200
    assert response.json()["trading_enabled"] is False
    assert client.post("/api/v1/meme-coins/robinhood/status", json={}).status_code == 405
    assert not any("order" in getattr(route, "path", "") or
                   "wallet" in getattr(route, "path", "") for route in app.routes)
