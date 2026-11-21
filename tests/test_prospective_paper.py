"""Offline prospective paper regression tests. No exchange data or broker."""
from datetime import datetime, time, timezone
import json
import math

import numpy as np
import pandas as pd
import pytest

from src.core.etf_rotation import RotationParams
from src.core.prospective_paper import observe_completed_close, check_hash
from src.services.prospective_paper_journal import read_journal, append_paper_record


DATES = pd.bdate_range("2026-11-09", periods=12)
PARAMS = RotationParams(lookback_days=2, rebalance="weekly", top_n=1, cost_bps=10.0)


def prices(change=None):
    amounts = [100.0 + i for i in range(len(DATES))]
    if change:
        for i, price in change.items():
            amounts[i] = price
    return pd.DataFrame({"510300": amounts}, index=DATES)


def observe(day_index, previous=None, frame=None, source="EfinanceFetcher",
            params=PARAMS, slippage=5.0, observed=None, next_index=None):
    ix = DATES if frame is None else frame.index
    day = ix[day_index].date()
    if next_index is None:
        next_index = day_index + 1
    at = observed or datetime.combine(day, time(10, 0), tzinfo=timezone.utc)
    return observe_completed_close(
        (prices() if frame is None else frame).iloc[:day_index + 1],
        asset_code="510300", params=params, source=source, as_of=day,
        next_session=ix[next_index].date(), observed_at_utc=at,
        previous=previous, slippage_bps=slippage,
    )


def test_initialization_does_not_replay_history_or_invest_at_signal_close():
    # First observation on Friday: signal is visible but not filled until Mon.
    first = observe(4)
    assert first["seq"] == 0 and first["session"] == "2026-11-13"
    assert first["signal"] and first["pending_target"] is True
    assert not first["invested"] and first["fill"] is None
    assert first["equity"] == 1.0 and first["return_pct"] == 0
    assert check_hash(first)


def test_friday_signal_fills_next_monday_close_and_only_then_earns_returns():
    fri = observe(4)
    mon = observe(5, fri)
    assert mon["fill"] == "BUY"
    assert mon["invested"] is True
    assert mon["pending_target"] is None
    assert mon["equity"] == pytest.approx(0.9985)
    # The strategy did not earn Fri -> Mon appreciation: was in cash.
    tue = observe(6, mon)
    assert tue["fill"] is None
    assert tue["equity"] == pytest.approx(mon["equity"] * 106 / 105)
    assert tue["return_pct"] == pytest.approx((tue["equity"] - 1) * 100)


def test_sell_signal_fills_only_at_next_close_and_charges_costs():
    original = prices({6: 104, 7: 102, 8: 97, 9: 92, 10: 90, 11: 88})
    fri = observe(4, frame=original)
    mon = observe(5, fri, frame=original)
    prior = mon
    for i in range(6, 10):
        prior = observe(i, prior, frame=original)
    assert prior["session"] == "2026-11-20"
    assert prior["signal"] and prior["pending_target"] is False
    assert prior["invested"] is True
    following = observe(10, prior, frame=original)
    assert following["fill"] == "SELL" and not following["invested"]


def test_idempotency_and_missing_days_are_refused():
    fri = observe(4)
    with pytest.raises(ValueError, match="out-of-order"):
        observe(4, fri)
    with pytest.raises(ValueError, match="out-of-order"):
        observe(6, fri)


def test_prior_price_revisions_or_provider_switch_block_paper_updates():
    fri = observe(4)
    changed = prices({4: 104.1})
    with pytest.raises(ValueError, match="revised"):
        observe(5, fri, frame=changed)
    with pytest.raises(ValueError, match="data source changed"):
        observe(5, fri, source="BaostockFetcher")
    with pytest.raises(ValueError, match="frozen paper rules"):
        observe(5, fri, params=RotationParams(lookback_days=2, cost_bps=12))


def test_future_prices_same_day_are_rejected():
    with pytest.raises(ValueError, match="must end"):
        observe_completed_close(
            prices(), asset_code="510300", params=PARAMS, source="TestFeed",
            as_of=DATES[4].date(), next_session=DATES[5].date(),
            observed_at_utc=datetime(2026, 11, 13, 10, tzinfo=timezone.utc),
            previous=None,
        )


def test_early_close_and_bad_market_observation_are_rejected():
    with pytest.raises(ValueError, match="before Shanghai market close"):
        observe(4, observed=datetime(2026, 11, 13, 6, tzinfo=timezone.utc))
    with pytest.raises(ValueError, match="timezone-aware"):
        observe(4, observed=datetime(2026, 11, 13, 10))
    with pytest.raises(ValueError, match="ETF code"):
        observe_completed_close(
            prices().iloc[:5], asset_code="AAA", params=PARAMS,
            source="X", as_of=DATES[4].date(), next_session=DATES[5].date(),
            observed_at_utc=datetime(2026, 11, 13, 10, tzinfo=timezone.utc),
            previous=None,
        )


def test_malformed_prices_and_non_binary_portfolio_fail_closed():
    bad = prices()
    bad.iloc[3, 0] = np.nan
    with pytest.raises(ValueError, match="finite"):
        observe(4, frame=bad)
    with pytest.raises(ValueError, match="top_n=1"):
        observe(4, params=RotationParams(top_n=2))


def test_hash_chain_append_restart_and_status(tmp_path):
    path = tmp_path / "paper.jsonl"
    friday = observe(4)
    append_paper_record(path, friday)
    assert read_journal(path) == [friday]
    monday = observe(5, read_journal(path)[-1])
    append_paper_record(path, monday)
    assert read_journal(path) == [friday, monday]
    assert monday["prev_hash"] == friday["hash"]
    assert path.stat().st_size > 0
    with pytest.raises(ValueError, match="stale or duplicate"):
        append_paper_record(path, monday)
    assert len(read_journal(path)) == 2


def test_corrupt_or_truncated_journals_fail_closed(tmp_path):
    path = tmp_path / "paper.jsonl"
    event = observe(4)
    append_paper_record(path, event)
    path.write_bytes(path.read_bytes()[:-1])
    with pytest.raises(ValueError, match="incomplete"):
        read_journal(path)
    path.write_text(json.dumps({**event, "equity": 1000}) + "\n")
    with pytest.raises(ValueError, match="hash"):
        read_journal(path)


def test_lockfile_prevents_concurrent_writer_and_requires_manual_recovery(tmp_path):
    path = tmp_path / "paper.jsonl"
    lock = tmp_path / "paper.jsonl.lock"
    lock.write_text("locked")
    with pytest.raises(FileExistsError):
        append_paper_record(path, observe(4))
    assert not path.exists()
    lock.unlink()
    append_paper_record(path, observe(4))
    assert len(read_journal(path)) == 1


def test_tampered_previous_record_never_used():
    first = observe(4)
    first["equity"] = 77
    assert not check_hash(first)
    with pytest.raises(ValueError, match="hash mismatch"):
        observe(5, first)
