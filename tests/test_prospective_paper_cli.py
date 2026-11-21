"""Manual CLI safety: preview has no writes and status has no network."""
from datetime import date, datetime, timezone
from types import SimpleNamespace

import pandas as pd
import pytest

from scripts.observe_etf_paper_v9 import parser, run
from scripts import observe_etf_paper_v9 as paper_cli
from src.services.prospective_paper_journal import read_journal



def _set_clock(monkeypatch, instant):
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return instant.astimezone(tz) if tz else instant.replace(tzinfo=None)

    monkeypatch.setattr(paper_cli, "datetime", FixedDatetime)


def _fake_provider(monkeypatch):
    import src.core.trading_calendar as cal
    import src.services.etf_rotation_service as svc

    latest = date(2026, 11, 13)  # Friday, close known

    # An actual prospective run uses the host clock, not a historical fixture.
    # Fix it explicitly here so the legitimate Friday commit remains realistic.
    _set_clock(monkeypatch, datetime(2026, 11, 13, 10, tzinfo=timezone.utc))
    index = pd.bdate_range(end="2026-11-13", periods=80)
    closes = pd.DataFrame({"510300": [100.0 + i * 0.12 for i in range(80)]}, index=index)
    seen = {"loads": 0}

    monkeypatch.setattr(cal, "get_effective_trading_date", lambda *_args, **_kw: latest)
    monkeypatch.setattr(cal, "get_next_trading_date", lambda *_args, **_kw: date(2026, 11, 16))
    monkeypatch.setattr(cal, "get_trading_dates", lambda *_args, **_kw: pd.DatetimeIndex(["2026-11-13"]))

    def load(_manager, codes, years, end=None):
        seen["loads"] += 1
        assert codes == ["510300"] and years == 2 and end == latest
        return SimpleNamespace(closes=closes, failed={}, sources={"510300": "MockAdjusted"})

    monkeypatch.setattr(svc, "load_closes", load)
    monkeypatch.setattr(svc, "data_quality_warnings", lambda _prices: [])
    return seen


def test_preview_is_not_write_and_status_is_offline(monkeypatch, tmp_path, capsys):
    journal = tmp_path / "observations.jsonl"
    seen = _fake_provider(monkeypatch)
    preview = parser().parse_args(["--journal", str(journal), "--asset", "510300"])
    assert preview.commit is False
    assert run(preview) == 0
    assert not journal.exists()
    assert seen["loads"] == 1
    assert "PREVIEW_ONLY" in capsys.readouterr().out

    status = parser().parse_args(["--journal", str(journal), "--status"])
    assert run(status) == 0
    assert "EMPTY" in capsys.readouterr().out
    assert not journal.exists()
    assert seen["loads"] == 1


def test_commit_explicitly_appends_only_one_completed_session(monkeypatch, tmp_path, capsys):
    journal = tmp_path / "observations.jsonl"
    seen = _fake_provider(monkeypatch)
    cmd = parser().parse_args(["--journal", str(journal), "--asset", "510300", "--commit"])
    assert run(cmd) == 0
    events = read_journal(journal)
    assert len(events) == 1
    assert events[0]["session"] == "2026-11-13"
    assert events[0]["next_session"] == "2026-11-16"
    assert events[0]["equity"] == 1.0
    assert events[0]["pending_target"] is True
    assert "RECORDED" in capsys.readouterr().out
    with pytest.raises(ValueError, match="out-of-order"):
        run(cmd)
    assert len(read_journal(journal)) == 1

    status = parser().parse_args(["--journal", str(journal), "--status"])
    assert run(status) == 0
    assert "PAPER_ONLY" in capsys.readouterr().out
    assert seen["loads"] == 2


def test_commit_rejects_weekend_backdating_and_never_opens_journal(monkeypatch, tmp_path):
    journal = tmp_path / "weekend.jsonl"
    seen = _fake_provider(monkeypatch)
    _set_clock(monkeypatch, datetime(2026, 11, 14, 10, tzinfo=timezone.utc))
    cmd = parser().parse_args(["--journal", str(journal), "--commit"])
    with pytest.raises(ValueError, match="historical catch-up forbidden"):
        run(cmd)
    assert seen["loads"] == 0
    assert not journal.exists()


def test_commit_rejects_pre_close_previous_session(monkeypatch, tmp_path):
    journal = tmp_path / "before-close.jsonl"
    seen = _fake_provider(monkeypatch)
    _set_clock(monkeypatch, datetime(2026, 11, 16, 3, tzinfo=timezone.utc))
    cmd = parser().parse_args(["--journal", str(journal), "--commit"])
    with pytest.raises(ValueError, match="pre-close"):
        run(cmd)
    assert seen["loads"] == 0
    assert not journal.exists()


def test_preview_can_inspect_last_completed_session_without_recording(monkeypatch, tmp_path, capsys):
    journal = tmp_path / "weekend-preview.jsonl"
    seen = _fake_provider(monkeypatch)
    _set_clock(monkeypatch, datetime(2026, 11, 14, 10, tzinfo=timezone.utc))
    cmd = parser().parse_args(["--journal", str(journal)])
    assert run(cmd) == 0
    assert "PREVIEW_ONLY" in capsys.readouterr().out
    assert seen["loads"] == 1
    assert not journal.exists()
