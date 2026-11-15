# -*- coding: utf-8 -*-
"""Offline tests for opt-in BIST100 OHLCV storage, never live Yahoo or trades."""
import builtins
from datetime import date
from types import SimpleNamespace

import pandas as pd
import pytest

from src.core.trading_calendar import get_market_for_stock
from src.services import bist100_import as importer


AS_OF = date(2026, 11, 15)
LAST = date(2026, 11, 13)


def _history():
    idx = pd.bdate_range(end="2026-11-13", periods=70)
    closes = [100.0 + i / 10 for i in range(len(idx))]
    return pd.DataFrame({
        "date": idx, "open": [100.0] * len(idx),
        "high": [115.0] * len(idx), "low": [90.0] * len(idx),
        "close": closes, "volume": [5000.0] * len(idx),
    })


class FakeDatabase:
    def __init__(self, fail_symbol=None):
        self.calls = []
        self.frames = {}
        self.fail_symbol = fail_symbol

    def save_daily_data(self, df, code, data_source, canonical_id=None):
        if code == self.fail_symbol:
            raise RuntimeError("disk full")
        self.calls.append((code, data_source, canonical_id, df.copy()))
        previous = set(self.frames[code]["date"]) if code in self.frames else set()
        self.frames[code] = df.copy()
        return len(set(df["date"]) - previous)

    def get_data_range(self, code, start, end):
        frame = self.frames.get(code)
        if frame is None:
            return []
        return [
            SimpleNamespace(date=day)
            for day in frame["date"]
            if start <= day <= end
        ]


@pytest.fixture(autouse=True)
def completed_session(monkeypatch):
    monkeypatch.setattr(importer, "_last_completed_session", lambda day: LAST)


def _run(*, symbols=("THYAO.IS",), db=None, write_db=False, history=None, currency=None):
    return importer.import_bist100_history(
        as_of=AS_OF, symbols=symbols, write_db=write_db, db=db,
        delay_seconds=0,
        fetch_history=history or (lambda *args: _history()),
        fetch_currency=currency or (lambda symbol: "TRY"),
    )


def test_bist_market_detection_does_not_import_unrelated_providers(monkeypatch):
    original = builtins.__import__

    def guard(name, *args, **kwargs):
        if name == "data_provider" or name.startswith("data_provider."):
            raise AssertionError("BIST market detection imported unrelated providers")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guard)
    assert get_market_for_stock("THYAO.IS") == "tr"
    assert get_market_for_stock("akfye.is") == "tr"


def test_dry_run_finds_valid_bars_but_never_opens_or_writes_database():
    db = FakeDatabase()
    report = _run(db=db)
    assert report["checked"] == 1
    assert report["ready_for_import"] == 1
    assert report["imported"] == report["new_rows"] == 0
    assert report["mode"] == "dry_run"
    assert db.calls == []
    assert report["results"][0]["storage_status"] == "dry_run"


def test_opt_in_import_uses_existing_stockdaily_schema_and_is_idempotent():
    db = FakeDatabase()
    report = _run(db=db, write_db=True)
    assert report["checked"] == report["ready_for_import"] == report["imported"] == 1
    assert report["new_rows"] == 70
    symbol, source, canonical_id, frame = db.calls[0]
    assert (symbol, source, canonical_id) == ("THYAO.IS", "Yahoo Finance", "THYAO.IS")
    assert frame["date"].max() == LAST
    assert {"date", "open", "high", "low", "close", "volume", "ma5", "ma10", "ma20", "pct_chg"}.issubset(frame.columns)
    assert round(frame["ma5"].iloc[-1], 4) == round(frame["close"].tail(5).mean(), 4)
    assert round(frame["pct_chg"].iloc[-1], 4) == round(
        100 * (frame["close"].iloc[-1] / frame["close"].iloc[-2] - 1), 4
    )
    again = _run(db=db, write_db=True)
    assert again["imported"] == 1
    assert again["new_rows"] == 0  # Existing bars upsert, not duplicate


def test_partial_current_bar_is_not_written():
    db = FakeDatabase()
    partial = _history()
    extra = partial.tail(1).copy()
    extra["date"] = pd.Timestamp("2026-11-15")
    frame = pd.concat([partial, extra], ignore_index=True)
    report = _run(db=db, write_db=True, history=lambda *args: frame)
    assert report["imported"] == 1
    assert db.calls[0][3]["date"].max() == LAST
    assert len(db.calls[0][3]) == 70


def test_stale_and_wrong_currency_are_blocked_before_database_writes():
    db = FakeDatabase()
    report = _run(
        symbols=("THYAO.IS", "AKFYE.IS"), db=db, write_db=True,
        currency=lambda sym: "USD" if sym == "AKFYE.IS" else "TRY",
        history=lambda sym, *args: _history() if sym == "AKFYE.IS" else _history().iloc[:-1],
    )
    assert report["ready_for_import"] == 0
    assert report["imported"] == 0
    assert report["coverage_status_counts"] == {"currency_mismatch": 1, "stale_price": 1}
    assert db.calls == []


def test_database_write_failure_is_visible_and_next_symbol_can_succeed():
    db = FakeDatabase(fail_symbol="THYAO.IS")
    report = _run(
        symbols=("THYAO.IS", "AKBNK.IS"), db=db, write_db=True,
    )
    assert report["checked"] == 2 and report["ready_for_import"] == 2
    assert report["imported"] == 1
    assert report["storage_status_counts"] == {"db_error": 1, "imported": 1}
    assert report["results"][0]["error_type"] == "RuntimeError"
    assert db.calls[0][0] == "AKBNK.IS"


@pytest.mark.parametrize("symbols", [
    (), ("THYAO.IS", "THYAO.IS"), ("XU100.IS",), ("AAPL",), ("THYAO",),
])
def test_reject_invalid_selection_before_fetch_or_persistence(symbols):
    db = FakeDatabase()
    with pytest.raises(ValueError, match="Selection"):
        _run(symbols=symbols, db=db, write_db=True,
             history=lambda *args: pytest.fail("Fetched despite invalid symbol"))
    assert db.calls == []


def test_database_opt_in_requires_functional_storage_object_before_fetch():
    with pytest.raises(ValueError, match="initialized StockDaily"):
        _run(db=object(), write_db=True,
             history=lambda *args: pytest.fail("Fetched before DB initialized"))
