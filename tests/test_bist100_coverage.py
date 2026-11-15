# -*- coding: utf-8 -*-
"""Offline BIST100 historical coverage contracts: no Yahoo traffic in CI."""
from datetime import date

import pandas as pd
import pytest

from src.services import bist100_coverage as coverage


AS_OF = date(2026, 11, 15)
LAST_COMPLETED = pd.DatetimeIndex(["2026-11-13"])


def _history(last="2026-11-13", count=70):
    dates = pd.bdate_range(end=last, periods=count)
    return pd.DataFrame({
        "date": dates,
        "open": [100.0] * count,
        "high": [101.0] * count,
        "low": [99.0] * count,
        "close": [100.5] * count,
        "volume": [1000] * count,
    })


def _audit(monkeypatch, history=None, currency="TRY", symbols=("THYAO.IS",), **kwargs):
    monkeypatch.setattr(coverage, "get_trading_dates", lambda *args: LAST_COMPLETED)
    loader = history if callable(history) else (lambda symbol, start, end: history if history is not None else _history())
    return coverage.scan_bist100_history(
        as_of=AS_OF, symbols=symbols, fetch_history=loader,
        fetch_currency=lambda symbol: currency,
        delay_seconds=0, **kwargs,
    )


def test_coverage_report_only_counts_completed_valid_try_bars(monkeypatch):
    report = _audit(monkeypatch)
    assert report["index"] == "BIST100"
    assert report["universe_total"] == 100
    assert report["checked"] == 1 and report["remaining"] == 99
    assert report["complete"] is False
    assert report["ready"] == 1 and report["with_valid_price_bars"] == 1
    assert report["expected_last_completed_session"] == "2026-11-13"
    assert report["results"][0]["last_bar_date"] == "2026-11-13"
    assert report["results"][0]["observed_currency"] == "TRY"
    assert "no stock analysis" in report["note"]


def test_coverage_report_separates_missing_stale_and_currency_issues(monkeypatch):
    def by_symbol(symbol, start, end):
        if symbol == "AKFYE.IS":
            return pd.DataFrame()
        if symbol == "ASELS.IS":
            return _history("2026-11-12")
        return _history()

    report = _audit(
        monkeypatch, history=by_symbol,
        symbols=("AKFYE.IS", "ASELS.IS", "THYAO.IS"),
    )
    assert report["status_counts"] == {"no_data": 1, "ready": 1, "stale_price": 1}
    assert report["ready"] == 1
    assert report["with_valid_price_bars"] == 2
    assert report["checked"] == 3 and not report["complete"]
    assert {v["symbol"]: v["status"] for v in report["results"]} == {
        "AKFYE.IS": "no_data", "ASELS.IS": "stale_price", "THYAO.IS": "ready",
    }


def test_currency_mismatch_and_unknown_do_not_count_ready(monkeypatch):
    mismatched = _audit(monkeypatch, currency="USD")
    unknown = _audit(monkeypatch, currency=None)
    assert mismatched["ready"] == unknown["ready"] == 0
    assert mismatched["results"][0]["status"] == "currency_mismatch"
    assert unknown["results"][0]["status"] == "currency_unverified"
    assert mismatched["with_valid_price_bars"] == 1


def test_currency_lookup_exception_is_visible_but_does_not_erase_price(monkeypatch):
    monkeypatch.setattr(coverage, "get_trading_dates", lambda *args: LAST_COMPLETED)
    def fail_currency(symbol):
        raise ConnectionError("metadata unavailable")
    report = coverage.scan_bist100_history(
        as_of=AS_OF, symbols=("THYAO.IS",),
        fetch_history=lambda *args: _history(),
        fetch_currency=fail_currency, delay_seconds=0,
    )
    record = report["results"][0]
    assert record["status"] == "currency_unverified"
    assert "currency_lookup_failed" in record["issues"]
    assert record["rows"] == 70


def test_calendar_unavailable_never_claims_fresh(monkeypatch):
    monkeypatch.setattr(coverage, "get_trading_dates", lambda *args: None)
    report = coverage.scan_bist100_history(
        as_of=AS_OF, symbols=("THYAO.IS",),
        fetch_history=lambda *args: _history(),
        fetch_currency=lambda *args: "TRY", delay_seconds=0,
    )
    assert report["ready"] == 0
    assert report["expected_last_completed_session"] is None
    assert report["results"][0]["status"] == "calendar_unavailable"


def test_todays_partial_bar_does_not_make_older_quote_fresh(monkeypatch):
    partial_bar = _history(count=1).copy()
    partial_bar["date"] = pd.to_datetime(["2026-11-15"])
    partial = pd.concat([_history(last="2026-11-12"), partial_bar], ignore_index=True)
    report = _audit(monkeypatch, history=partial)
    assert report["ready"] == 0
    assert report["results"][0]["status"] == "stale_price"
    assert report["results"][0]["last_bar_date"] == "2026-11-12"


@pytest.mark.parametrize("data", [
    pd.DataFrame({"date": [pd.Timestamp("2026-11-13")], "close": [2.0]}),
    _history().assign(close=float("nan")),
    _history().assign(volume=-1),
    _history().assign(high=1),
    pd.concat([_history(), _history().tail(1)]),
])
def test_invalid_ohlcv_is_not_silently_analyzable(monkeypatch, data):
    report = _audit(monkeypatch, history=data)
    assert report["ready"] == 0
    assert report["results"][0]["status"] == "invalid_data"


def test_insufficient_history_and_fetch_failure_are_separate(monkeypatch):
    short = _audit(monkeypatch, history=_history(count=4))
    assert short["results"][0]["status"] == "insufficient_history"

    def offline_error(*args):
        raise RuntimeError("network down")
    error = _audit(monkeypatch, history=offline_error)
    assert error["results"][0]["status"] == "fetch_error"
    assert error["results"][0]["error_type"] == "RuntimeError"
    assert error["ready"] == 0


def test_invalid_and_stale_selection_rejected_before_any_request(monkeypatch):
    calls = []
    def called(*args):
        calls.append(args)
        return _history()
    monkeypatch.setattr(coverage, "get_trading_dates", lambda *args: LAST_COMPLETED)
    for names in [("XU100.IS",), ("THYAO.IS", "THYAO.IS"), ("AAPL",), ()]:
        with pytest.raises(ValueError, match="selection|empty"):
            coverage.scan_bist100_history(
                as_of=AS_OF, symbols=names,
                fetch_history=called, fetch_currency=lambda *args: "TRY", delay_seconds=0,
            )
    with pytest.raises(ValueError, match="not valid"):
        coverage.scan_bist100_history(
            as_of=date(2027, 1, 1), symbols=("THYAO.IS",),
            fetch_history=called, fetch_currency=lambda *args: "TRY", delay_seconds=0,
        )
    assert calls == []


def test_full_100_member_audit_can_record_all_no_data_without_fabrication(monkeypatch):
    monkeypatch.setattr(coverage, "get_trading_dates", lambda *args: LAST_COMPLETED)
    report = coverage.scan_bist100_history(
        as_of=AS_OF, fetch_history=lambda *args: pd.DataFrame(),
        fetch_currency=lambda *args: "TRY", delay_seconds=0,
    )
    assert report["complete"] is True
    assert report["universe_total"] == report["checked"] == 100
    assert report["ready"] == 0
    assert report["status_counts"] == {"no_data": 100}
    assert len(report["results"]) == 100


def test_existing_yahoo_fetcher_empty_result_is_reported_as_no_data(monkeypatch):
    from data_provider.base import DataFetchError
    from data_provider.yfinance_fetcher import YfinanceFetcher

    def missing(*args, **kwargs):
        raise DataFetchError("Yahoo Finance 未查询到 THYAO.IS 的数据")

    monkeypatch.setattr(YfinanceFetcher, "get_daily_data", missing)
    history = coverage._yahoo_daily_history("THYAO.IS", AS_OF, AS_OF)
    assert history.empty


def test_other_yahoo_provider_failures_are_not_mislabeled_missing(monkeypatch):
    from data_provider.base import DataFetchError
    from data_provider.yfinance_fetcher import YfinanceFetcher

    def throttled(*args, **kwargs):
        raise DataFetchError("Yahoo Finance 429 rate limited")

    monkeypatch.setattr(YfinanceFetcher, "get_daily_data", throttled)
    with pytest.raises(DataFetchError, match="429"):
        coverage._yahoo_daily_history("THYAO.IS", AS_OF, AS_OF)


def test_calendar_exception_fails_closed_instead_of_aborting_all_stocks(monkeypatch):
    def calendar_error(*args):
        raise RuntimeError("XIST calendar unavailable")
    monkeypatch.setattr(coverage, "get_trading_dates", calendar_error)
    report = coverage.scan_bist100_history(
        as_of=AS_OF, symbols=("THYAO.IS",),
        fetch_history=lambda *args: _history(),
        fetch_currency=lambda *args: "TRY", delay_seconds=0,
    )
    assert report["results"][0]["status"] == "calendar_unavailable"
    assert report["ready"] == 0


def test_cli_explicit_five_stocks_and_atomic_report(monkeypatch, tmp_path, capsys):
    import json
    import sys

    wanted = ("THYAO.IS", "ASELS.IS", "AKBNK.IS", "TUPRS.IS", "AKFYE.IS")
    captured = []

    def fake_scan(**kwargs):
        captured.append(kwargs["symbols"])
        return {"index": "BIST100", "checked": len(kwargs["symbols"]), "note": "offline test"}

    target = tmp_path / "saved-coverage.json"
    target.write_text("old report", encoding="utf-8")
    monkeypatch.setattr(coverage, "scan_bist100_history", fake_scan)
    monkeypatch.setattr(sys, "argv", [
        "bist100_coverage", "--as-of", "2026-11-15",
        "--symbols", ",".join(wanted), "--delay-seconds", "0",
        "--output", str(target),
    ])
    coverage.main()
    parsed = json.loads(target.read_text(encoding="utf-8"))
    assert captured == [wanted]
    assert parsed["checked"] == 5
    assert json.loads(capsys.readouterr().out) == parsed
    assert list(tmp_path.iterdir()) == [target]


@pytest.mark.parametrize("selection", [
    "THYAO.IS,THYAO.IS", "XU100.IS", "AAPL", "THYAO", "THYAO.IS,",
])
def test_cli_rejects_invalid_five_stock_selection_before_yahoo(monkeypatch, selection):
    import sys

    monkeypatch.setattr(sys, "argv", [
        "bist100_coverage", "--as-of", "2026-11-15", "--symbols", selection,
    ])
    with pytest.raises(SystemExit) as exc:
        coverage.main()
    assert exc.value.code == 2


def test_cli_rejects_combining_limit_and_symbols(monkeypatch):
    import sys

    monkeypatch.setattr(sys, "argv", [
        "bist100_coverage", "--as-of", "2026-11-15",
        "--limit", "5", "--symbols", "THYAO.IS,ASELS.IS",
    ])
    with pytest.raises(SystemExit) as exc:
        coverage.main()
    assert exc.value.code == 2
