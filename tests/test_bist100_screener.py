# -*- coding: utf-8 -*-
"""Offline, no-orders tests for the read-only BIST100 technical ranking."""
from datetime import date
import sqlite3
from types import SimpleNamespace

import pandas as pd
import pytest

from src.services.bist100_screener import (
    ReadOnlyStockDaily,
    screen_bist100_from_db,
)

DAY = date(2026, 11, 15)
SESSION = date(2026, 11, 13)


def _bars(symbol, *, count=80, source="Yahoo Finance", canonical=None, end="2026-11-13"):
    days = pd.bdate_range(end=end, periods=count)
    return [
        {
            "date": day.date(), "open": 90.0 + idx / 5,
            "high": 95.0 + idx / 5, "low": 85.0 + idx / 5,
            "close": 91.0 + idx / 5, "volume": 1000.0 + idx,
            "data_source": source,
            "canonical_id": symbol if canonical is None else canonical,
        }
        for idx, day in enumerate(days)
    ]


class FakeDb:
    def __init__(self, stocks=None, failing=None):
        self.stocks = stocks or {}
        self.failing = failing
        self.read_calls = []

    def get_data_range(self, code, start, end):
        self.read_calls.append((code, start, end))
        if code == self.failing:
            raise sqlite3.OperationalError("no such table: stock_daily")
        return [row for row in self.stocks.get(code, []) if start <= row["date"] <= end]


def _analyzer(scores=None, bias=None, failures=()):
    scores = scores or {}
    bias = bias or {}

    def analyze(frame, code):
        if code in failures:
            raise RuntimeError("model failed")
        assert frame["date"].max() == SESSION
        assert len(frame) >= 60
        return SimpleNamespace(
            signal_score=scores.get(code, 67), current_price=100.0,
            ma5=99.0, ma20=95.0, rsi_12=57.0,
            macd_bar=1.25, bias_ma5=bias.get(code, 1.0),
            trend_status=SimpleNamespace(name="BULL"),
            buy_signal=SimpleNamespace(name="BUY"),
        )

    return analyze


def _run(db, *, symbols=("THYAO.IS",), analyze=None, last_session=SESSION, **kwargs):
    return screen_bist100_from_db(
        as_of=DAY, symbols=symbols, db=db,
        analyze=analyze or _analyzer(), last_session=last_session,
        **kwargs,
    )


def test_fresh_rows_produce_a_scored_technical_ranking():
    db = FakeDb({"THYAO.IS": _bars("THYAO.IS")})
    report = _run(db)
    assert report["mode"] == "read_only_local_sqlite"
    assert report["checked"] == report["analyzed"] == 1
    assert report["remaining"] == 99
    assert report["status_counts"] == {"analyzed": 1}
    assert report["ranking"][0] == {
        "symbol": "THYAO.IS", "status": "analyzed", "bars": 80,
        "last_bar_date": SESSION.isoformat(), "score": 67,
        "close_try": 100.0, "ma5_try": 99.0, "ma20_try": 95.0,
        "rsi12": 57.0, "macd_histogram": 1.25, "bias_ma5_pct": 1.0,
        "trend": "Yükseliş", "technical_signal": "Alım sinyali",
        "chase_risk": False, "eligible_for_watchlist": True, "rank": 1,
    }
    assert len(db.read_calls) == 1


def test_missing_and_stale_stock_are_excluded_from_ranked_candidates():
    stocks = {
        "THYAO.IS": _bars("THYAO.IS", end="2026-11-12"),
        "AKBNK.IS": _bars("AKBNK.IS"),
    }
    result = _run(FakeDb(stocks), symbols=("THYAO.IS", "ASELS.IS", "AKBNK.IS"))
    assert result["checked"] == 3 and result["analyzed"] == 1
    assert result["status_counts"] == {
        "analyzed": 1, "not_imported": 1, "stale_price": 1,
    }
    assert [row["symbol"] for row in result["ranking"]] == ["AKBNK.IS"]


def test_insufficient_or_untrusted_source_is_excluded():
    stocks = {
        "THYAO.IS": _bars("THYAO.IS", count=45),
        "AKBNK.IS": _bars("AKBNK.IS", source="Unknown"),
        "ASELS.IS": _bars("ASELS.IS", canonical="ASELS"),
    }
    report = _run(FakeDb(stocks), symbols=tuple(stocks))
    assert report["analyzed"] == 0
    assert report["status_counts"] == {
        "insufficient_history": 1, "unverified_source": 2,
    }


def test_chase_risk_is_never_promoted_to_watchlist_eligible():
    stocks = {"THYAO.IS": _bars("THYAO.IS")}
    report = _run(FakeDb(stocks), analyze=_analyzer(bias={"THYAO.IS": 7.1}))
    assert report["ranking"][0]["score"] == 67
    assert report["ranking"][0]["technical_signal"] == "Alım sinyali"
    assert report["ranking"][0]["chase_risk"] is True
    assert report["ranking"][0]["eligible_for_watchlist"] is False
    assert report["watchlist_eligible"] == 0


def test_score_ties_use_symbol_order_and_failures_do_not_break_scan():
    stocks = {code: _bars(code) for code in ("THYAO.IS", "AKBNK.IS", "ASELS.IS")}
    report = _run(
        FakeDb(stocks, failing="ASELS.IS"),
        symbols=("THYAO.IS", "AKBNK.IS", "ASELS.IS"),
        analyze=_analyzer(scores={"THYAO.IS": 70, "AKBNK.IS": 70}),
    )
    assert report["analyzed"] == 2
    assert [x["symbol"] for x in report["ranking"]] == ["AKBNK.IS", "THYAO.IS"]
    assert [x["rank"] for x in report["ranking"]] == [1, 2]
    assert report["status_counts"] == {"analyzed": 2, "db_error": 1}


def test_duplicate_dates_or_invalid_ohlcv_never_reach_analyzer():
    bad = _bars("THYAO.IS")
    bad[-2]["date"] = bad[-1]["date"]
    invoked = []

    def analyzer(frame, code):
        invoked.append(code)
        raise AssertionError("Should have been gated")
    report = _run(FakeDb({"THYAO.IS": bad}), analyze=analyzer)
    assert report["status_counts"] == {"invalid_data": 1}
    assert invoked == []


def test_nonfinite_analyzer_output_is_not_ranked():
    report = _run(
        FakeDb({"THYAO.IS": _bars("THYAO.IS")}),
        analyze=_analyzer(scores={"THYAO.IS": float("nan")}),
    )
    assert report["analyzed"] == 0
    assert report["status_counts"] == {"analysis_error": 1}


@pytest.mark.parametrize("symbols", [
    (), ("AAPL",), ("XU100.IS",), ("THYAO.IS", "THYAO.IS"), ("THYAO",),
])
def test_only_unique_valid_snapshot_members_can_be_screened(symbols):
    db = FakeDb()
    with pytest.raises(ValueError, match="unique active"):
        _run(db, symbols=symbols)
    assert db.read_calls == []


def test_calendar_must_prove_a_past_completed_session():
    db = FakeDb({"THYAO.IS": _bars("THYAO.IS")})
    with pytest.raises(ValueError, match="verified completed"):
        _run(db, last_session=DAY)
    assert db.read_calls == []


def test_outdated_membership_snapshot_is_rejected():
    with pytest.raises(ValueError, match="not valid"):
        screen_bist100_from_db(
            as_of=date(2027, 1, 1), symbols=("THYAO.IS",),
            db=FakeDb(), analyze=_analyzer(), last_session=SESSION,
        )


def test_original_stock_trend_analyzer_runs_on_local_bist_history():
    from src.stock_analyzer import StockTrendAnalyzer

    report = _run(
        FakeDb({"THYAO.IS": _bars("THYAO.IS")}),
        analyze=StockTrendAnalyzer().analyze,
    )
    assert report["status_counts"] == {"analyzed": 1}
    assert 0 <= report["ranking"][0]["score"] <= 100
    assert report["ranking"][0]["ma5_try"] > 0
    assert 0 <= report["ranking"][0]["rsi12"] <= 100


def test_read_only_sqlite_refuses_all_writes(tmp_path):
    location = tmp_path / "stock_analysis.db"
    with sqlite3.connect(location) as connection:
        connection.execute(
            "CREATE TABLE stock_daily "
            "(code TEXT, date TEXT, open REAL, high REAL, low REAL, "
            "close REAL, volume REAL, data_source TEXT, canonical_id TEXT)"
        )
        connection.execute(
            "INSERT INTO stock_daily VALUES (?,?,?,?,?,?,?,?,?)",
            ("THYAO.IS", "2026-11-13", 1, 2, 0.5, 1.5, 200, "Yahoo Finance", "THYAO.IS"),
        )
    with ReadOnlyStockDaily(location) as db:
        records = db.get_data_range("THYAO.IS", date(2026, 11, 1), SESSION)
        assert len(records) == 1
        with pytest.raises(sqlite3.OperationalError):
            db.connection.execute("DELETE FROM stock_daily")
    assert location.exists()


def test_read_only_sqlite_never_creates_a_missing_database(tmp_path):
    location = tmp_path / "missing.db"
    with pytest.raises(FileNotFoundError):
        ReadOnlyStockDaily(location)
    assert not location.exists()
