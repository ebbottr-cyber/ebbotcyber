"""Offline conversion of recorded Jupiter V2 quotes into deterministic paper replay."""
from __future__ import annotations

from copy import deepcopy

import pytest

from src.services.meme_coin_jupiter_quotes import (
    USDC_MINT, normalize_quote,
)
from src.services.meme_coin_quote_bridge import (
    capture_to_event, replay_captured_quotes,
)
from src.services.meme_coin_paper_replay import replay

TOKEN = "11111111111111111111111111111111"


def capture(
    side="buy", *, strategy="new_launch", input_raw="25000000",
    output_raw="100000000", observed=1000000,
):
    request = {
        "source": "jupiter_swap_v2_order_quote_only",
        "strategy": strategy,
        "mint": TOKEN,
        "side": side,
        "input_mint": USDC_MINT if side == "buy" else TOKEN,
        "output_mint": TOKEN if side == "buy" else USDC_MINT,
        "amount_in_raw": input_raw,
    }
    response = {
        "inAmount": input_raw, "outAmount": output_raw,
        "router": "metis", "feeBps": 2, "transaction": None,
    }
    return normalize_quote(request, response, observed_at_ms=observed)


def record(quote, **kwargs):
    data = {
        "quote": quote, "token_decimals": 6,
        "attempted_at_ms": quote["captured_at_ms"] + 300,
        "network_fee_usd": "0.01", "priority_fee_usd": "0.00",
        "modeled_adverse_slippage_bps": 0,
        "outcome": "success",
    }
    data.update(kwargs)
    return data


def test_buy_and_later_sell_captured_quotes_to_separate_paper_ledgers():
    buy = record(capture())
    sell = record(capture(
        "sell", input_raw="99000000", output_raw="30000000", observed=2000000,
    ))
    independent_buy = record(capture(
        strategy="momentum", input_raw="10000000",
        output_raw="40000000", observed=3000000,
    ))
    report = replay_captured_quotes([buy, sell, independent_buy])
    a = report["ledgers"]["new_launch"]
    b = report["ledgers"]["momentum"]
    assert report["mode"] == "offline_recorded_quote_scenarios"
    assert report["recorded_quote_source"] == "jupiter_swap_v2_order_quote_only"
    assert report["data_is_live"] is False
    assert report["live_trading_enabled"] is False
    assert report["simulation_is_realized_return"] is False
    assert report["capture_provenance_cryptographically_verified"] is False
    assert report["fees_and_failure_outcomes_are_scenario_assumptions"] is True
    assert report["this_is_actual_performance"] is False
    assert report["capture_ids"] == [
        buy["quote"]["capture_id"],
        sell["quote"]["capture_id"],
        independent_buy["quote"]["capture_id"],
    ]
    assert a["successful_buys"] == 1
    assert a["successful_sells"] == 1
    assert a["cash_usd"] == "1004.98"
    assert a["realized_pnl_usd"] == "5.23"
    assert a["positions"][TOKEN]["quantity"] == "1.000000000"
    assert b["cash_usd"] == "989.99"
    assert b["realized_pnl_usd"] == "0.00"
    assert b["positions"][TOKEN]["quantity"] == "40.000000000"
    assert a["audit"][0]["execution_is_real"] is False


def test_bridge_preserves_quote_only_and_does_not_double_charge_provider_fee():
    r = record(capture())
    event = capture_to_event(r)
    assert event["amount_in"] == "25"
    assert event["expected_out"] == "100"
    assert event["source"] == "offline_fixture"
    assert event["network_fee_usd"] == "0.01"
    assert event["priority_fee_usd"] == "0"
    assert event["modeled_adverse_slippage_bps"] == 0
    output = replay([event])["ledgers"]["new_launch"]
    assert output["cash_usd"] == "974.99"
    assert output["positions"][TOKEN]["quantity"] == "100.000000000"


def test_scenario_failure_charges_given_fee_but_never_trades():
    r = record(capture(), outcome="onchain_failure", network_fee_usd="0.03")
    result = replay_captured_quotes([r])
    a = result["ledgers"]["new_launch"]
    assert a["cash_usd"] == "999.97"
    assert a["failed_transactions"] == 1
    assert a["positions"] == {}


@pytest.mark.parametrize("mutator", [
    lambda x: x["quote"].update({"amount_out_raw": "100000001"}),
    lambda x: x["quote"].update({"capture_id": "000"}),
    lambda x: x["quote"].update({"mint": USDC_MINT}),
    lambda x: x["quote"].update({"input_mint": TOKEN}),
    lambda x: x["quote"].update({"execution_is_real": True}),
    lambda x: x["quote"].update({"transaction_returned": True}),
    lambda x: x.update({"token_decimals": 18}),
    lambda x: x.update({"token_decimals": True}),
    lambda x: x.update({"attempted_at_ms": x["quote"]["captured_at_ms"] + 3001}),
    lambda x: x.update({"attempted_at_ms": x["quote"]["captured_at_ms"] - 1}),
    lambda x: x.update({"modeled_adverse_slippage_bps": 1500}),
    lambda x: x.update({"network_fee_usd": "NaN"}),
    lambda x: x.update({"outcome": "signed_order"}),
    lambda x: x.update({"private_key": "never"}),
])
def test_tampering_bad_scenario_or_unapproved_fields_are_rejected(mutator):
    x = deepcopy(record(capture()))
    mutator(x)
    with pytest.raises((ValueError, TypeError, KeyError)):
        capture_to_event(x)


def test_replay_rejects_duplicate_quote_captures_and_nonchronological_orders():
    one = record(capture())
    with pytest.raises(ValueError, match="duplicate_event_id"):
        replay_captured_quotes([one, deepcopy(one)])
    two = record(capture(observed=10000))
    with pytest.raises(ValueError, match="non_chronological"):
        replay_captured_quotes([one, two])


def test_strategy_id_must_match_normalized_capture_identity():
    x = record(capture())
    x["quote"]["strategy"] = "momentum"
    with pytest.raises(ValueError):
        capture_to_event(x)
