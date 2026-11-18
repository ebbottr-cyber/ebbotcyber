"""Offline contracts for V10 read-only import and operator health status."""
from datetime import datetime, time, timezone
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd
import pytest
from fastapi import HTTPException

from src.core.etf_rotation import RotationParams
from src.core.prospective_paper import observe_completed_close
from src.services.paper_journal_reporting import inspect_paper_journal_text
from api.v1.endpoints import strategy_lab
from scripts import run_etf_paper_daily_v10 as daily


def _journal():
    idx = pd.bdate_range("2026-11-09", periods=8)
    frame = pd.DataFrame({"510300": [100.0 + i for i in range(8)]}, index=idx)
    params = RotationParams(lookback_days=2, rebalance="weekly", cost_bps=10)
    first = observe_completed_close(
        frame.iloc[:5], asset_code="510300", params=params, source="MockAdjusted",
        as_of=idx[4].date(), next_session=idx[5].date(),
        observed_at_utc=datetime(2026, 11, 13, 10, tzinfo=timezone.utc),
        previous=None, slippage_bps=5,
    )
    second = observe_completed_close(
        frame.iloc[:6], asset_code="510300", params=params, source="MockAdjusted",
        as_of=idx[5].date(), next_session=idx[6].date(),
        observed_at_utc=datetime(2026, 11, 16, 10, tzinfo=timezone.utc),
        previous=first, slippage_bps=5,
    )
    return [first, second]


def _text(events):
    return "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in events)


def test_import_validates_chain_and_only_returns_sanitized_metrics():
    result = inspect_paper_journal_text(_text(_journal()))
    assert result["status"] == "PAPER_ONLY"
    assert result["asset_code"] == "510300"
    assert result["source"] == "MockAdjusted"
    assert result["verified_hash_chain"] is True
    assert result["record_count"] == 2
    assert result["paper_buy_count"] == 1
    assert result["paper_sell_count"] == 0
    assert result["observed_return_pct"] == pytest.approx(-0.15)
    assert result["observed_max_drawdown_pct"] == pytest.approx(0.15)
    assert result["events"][-1]["paper_fill"] == "BUY"
    assert "hash" not in result
    assert "rules" not in result
    assert "observed_at_utc" not in result["events"]


def test_import_refuses_missing_newline_corruption_and_oversize():
    text = _text(_journal())
    with pytest.raises(ValueError, match="incomplete"):
        inspect_paper_journal_text(text.rstrip("\n"))
    bad = _journal()
    bad[1]["equity"] = 300
    with pytest.raises(ValueError, match="hash mismatch"):
        inspect_paper_journal_text(_text(bad))
    with pytest.raises(ValueError, match="exceeds"):
        inspect_paper_journal_text("x" * 524289)
    with pytest.raises(ValueError, match="empty"):
        inspect_paper_journal_text("")


def test_import_api_requires_existing_admin_auth_even_if_called_without_middleware(monkeypatch):
    monkeypatch.setattr(strategy_lab, "is_auth_enabled", lambda: False)
    inspector = Mock()
    monkeypatch.setattr(strategy_lab, "inspect_paper_journal_text", inspector)
    with pytest.raises(HTTPException) as exc:
        strategy_lab.inspect_paper_journal(strategy_lab.PaperJournalInspectRequest(journal_jsonl=_text(_journal())))
    assert exc.value.status_code == 403
    inspector.assert_not_called()


def test_import_api_on_protected_route_returns_summary_not_persistent_file(monkeypatch):
    monkeypatch.setattr(strategy_lab, "is_auth_enabled", lambda: True)
    text = _text(_journal())
    result = strategy_lab.inspect_paper_journal(
        strategy_lab.PaperJournalInspectRequest(journal_jsonl=text)
    )
    assert result["record_count"] == 2
    assert result["research_only"] is True
    with pytest.raises(HTTPException) as exc:
        strategy_lab.inspect_paper_journal(
            strategy_lab.PaperJournalInspectRequest(journal_jsonl="bad\n")
        )
    assert exc.value.status_code == 422


def test_daily_wrapper_preview_status_and_failure_no_implicit_notifications(monkeypatch, tmp_path):
    journal, health = tmp_path / "journal.jsonl", tmp_path / "health.json"
    cmd = daily.parser().parse_args(["--journal", str(journal), "--status-file", str(health)])
    fake = Mock(return_value=0)
    notifier = Mock()
    monkeypatch.setattr(daily, "run_paper", fake)
    monkeypatch.setattr(daily, "_send_failure_alert", notifier)
    assert daily.execute(cmd) == 0
    assert json.loads(health.read_text())["status"] == "PREVIEW_ONLY"
    assert not journal.exists()
    assert fake.call_count == 1
    notifier.assert_not_called()

    fake.side_effect = ValueError("sensitive operator path /secret/not-leaked")
    assert daily.execute(cmd) == 1
    status = json.loads(health.read_text())
    assert status["status"] == "BLOCKED"
    assert status["error_type"] == "ValueError"
    assert "/secret/" not in health.read_text()
    notifier.assert_not_called()


def test_daily_wrapper_opt_in_notify_and_safeguard_health_path(monkeypatch, tmp_path):
    journal, health = tmp_path / "journal.jsonl", tmp_path / "health.json"
    cmd = daily.parser().parse_args([
        "--journal", str(journal), "--status-file", str(health),
        "--commit", "--notify-on-error",
    ])
    monkeypatch.setattr(daily, "run_paper", Mock(side_effect=ValueError("provider unavailable")))
    delivered = Mock(return_value=True)
    monkeypatch.setattr(daily, "_send_failure_alert", delivered)
    assert daily.execute(cmd) == 1
    data = json.loads(health.read_text())
    assert data["status"] == "BLOCKED"
    assert data["notification_delivered"] is True
    assert delivered.call_count == 1
    cmd.status_file = journal
    with pytest.raises(ValueError, match="status and journal|cannot replace"):
        daily.execute(cmd)
