"""Offline tests for walletless Jupiter Swap V2 quote capture and read-only API."""
from __future__ import annotations

import json
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.v1.endpoints.meme_coin import router
from src.services import meme_coin_jupiter_quotes as quotes

TOKEN = "11111111111111111111111111111111"
USDC = quotes.USDC_MINT


def response(amount="25000000", output="100000000"):
    return {
        "inputMint": USDC, "outputMint": TOKEN,
        "inAmount": amount, "outAmount": output,
        "router": "metis", "feeBps": 2,
        "transaction": None,
    }


def test_off_by_default_and_never_contacts_jupiter():
    with patch.dict("os.environ", {"MEME_COIN_JUPITER_QUOTES_ENABLED": "false"}):
        with patch.object(quotes, "fetch_order_quote") as fetch:
            state = quotes.quote_preview("new_launch", TOKEN, "buy", 25000000)
    fetch.assert_not_called()
    assert state["status"] == "disabled"
    assert state["quote"] is None
    assert state["transaction_requested"] is False
    assert state["tradable"] is False


def test_strict_query_only_order_v2_uses_no_taker_or_other_transaction_fields():
    class ProviderResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self, *_):
            return json.dumps(response()).encode()

    def check_request(req, timeout=None):
        assert timeout <= 7
        assert req.get_method() == "GET"
        assert req.full_url.startswith(quotes.JUPITER_ORDER_ENDPOINT + "?")
        parts = urlsplit(req.full_url)
        params = parse_qs(parts.query)
        assert params == {
            "inputMint": [USDC], "outputMint": [TOKEN],
            "amount": ["25000000"],
        }
        assert not any(forbidden in req.full_url for forbidden in (
            "taker", "payer", "execute", "build", "swap/v1", "referral",
        ))
        return ProviderResponse()

    with patch.dict("os.environ", {"JUPITER_API_KEY": ""}):
        with patch.object(quotes, "urlopen", side_effect=check_request):
            raw = quotes.fetch_order_quote(USDC, TOKEN, "25000000")
    assert raw["outAmount"] == "100000000"


def test_full_capture_sanitizes_opaque_provider_data_and_reports_no_transactions():
    quotes._LAST_REQUEST_MONOTONIC = None
    upstream = {**response(), "routePlan": [{"secretly": "opaque"}], "requestId": "some-data"}
    with patch.dict("os.environ", {"MEME_COIN_JUPITER_QUOTES_ENABLED": "true"}):
        with patch.object(quotes, "fetch_order_quote", return_value=upstream) as fetch:
            item = quotes.quote_preview("new_launch", TOKEN, "buy", 25000000)
    assert fetch.call_args.args == (USDC, TOKEN, "25000000")
    assert item["status"] == "ok"
    assert item["live_quote_preview"] is True
    assert item["tradable"] is False
    assert item["quote"]["amount_out_raw"] == "100000000"
    assert item["quote"]["fee_bps"] == 2
    assert item["quote"]["transaction_returned"] is False
    assert "routePlan" not in item["quote"]
    assert "requestId" not in item["quote"]
    assert "secretly" not in json.dumps(item)


def test_sell_direction_uses_raw_token_units_and_quotes_usdc():
    req = quotes._base("momentum", TOKEN, "sell", 100000000)
    assert req["input_mint"] == TOKEN
    assert req["output_mint"] == USDC
    raw = {
        "inAmount": "100000000",
        "outAmount": "25000000", "router": "metis", "feeBps": 0,
        "transaction": None,
    }
    parsed = quotes.normalize_quote(req, raw, observed_at_ms=1000000)
    assert parsed["side"] == "sell"
    assert parsed["amount_in_raw"] == "100000000"
    assert parsed["amount_out_raw"] == "25000000"


@pytest.mark.parametrize("change", [
    {"transaction": "base64-signed-transaction"},
    {"inputMint": TOKEN},
    {"outputMint": USDC},
    {"inAmount": "25000001"},
    {"outAmount": "0"},
    {"router": ""},
    {"feeBps": 501},
    {"error": "no route found"},
    {"feeBps": True},
])
def test_invalid_or_non_quote_provider_payload_is_rejected(change):
    request = quotes._base("new_launch", TOKEN, "buy", 25000000)
    raw = {**response(), **change}
    with pytest.raises(ValueError):
        quotes.normalize_quote(request, raw, observed_at_ms=1000000)


def test_rate_limit_enforced_across_strategies_on_keyless_requests():
    quotes._LAST_REQUEST_MONOTONIC = None
    with patch.dict("os.environ", {"MEME_COIN_JUPITER_QUOTES_ENABLED": "true"}):
        with patch.object(quotes, "fetch_order_quote", return_value=response()) as fetch:
            a = quotes.quote_preview("new_launch", TOKEN, "buy", 25000000)
            b = quotes.quote_preview("momentum", TOKEN, "buy", 25000000)
    assert a["status"] == "ok"
    assert b["status"] == "rate_limited"
    assert b["quote"] is None
    assert fetch.call_count == 1


def test_unavailable_provider_is_reported_as_error_not_fabricated_price():
    quotes._LAST_REQUEST_MONOTONIC = None
    with patch.dict("os.environ", {"MEME_COIN_JUPITER_QUOTES_ENABLED": "true"}):
        with patch.object(quotes, "fetch_order_quote", side_effect=RuntimeError("bad route")):
            item = quotes.quote_preview("new_launch", TOKEN, "buy", 25000000)
    assert item["status"] == "unavailable"
    assert item["quote"] is None
    assert item["live_quote_preview"] is False


def test_invalid_mints_and_unbounded_amounts_refused():
    for mint in ("bad", USDC, quotes.WSOL_MINT):
        with pytest.raises(ValueError):
            quotes.quote_preview("new_launch", mint, "buy", 25000000)
    with pytest.raises(ValueError):
        quotes.quote_preview("new_launch", TOKEN, "buy", -1)
    with pytest.raises(ValueError):
        quotes.quote_preview("robinhood_chain", TOKEN, "buy", 25)
    with pytest.raises(ValueError):
        quotes.quote_preview("new_launch", TOKEN, "buy", 10**20)


def test_status_endpoint_read_only_and_no_request_when_disabled():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/meme-coins")
    client = TestClient(app)
    with patch.dict("os.environ", {"MEME_COIN_JUPITER_QUOTES_ENABLED": "false"}):
        response_api = client.get("/api/v1/meme-coins/solana/quote-preview", params={
            "strategy": "momentum", "side": "sell", "mint": TOKEN,
            "amount_raw": 1000000,
        })
    assert response_api.status_code == 200
    assert response_api.json()["status"] == "disabled"
    assert response_api.json()["transaction_submitted"] is False
    assert client.get("/api/v1/meme-coins/solana/quote-preview", params={
        "strategy": "robinhood_chain", "side": "buy", "mint": TOKEN,
        "amount_raw": 25000000,
    }).status_code == 422
    assert client.post("/api/v1/meme-coins/solana/quote-preview", json={}).status_code == 405
    assert not any("execute" in getattr(r, "path", "") or "swap" in getattr(r, "path", "")
                   for r in app.routes)
