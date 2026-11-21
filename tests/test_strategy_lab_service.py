"""Offline contract tests: guarded data provider bridge and research API."""
from dataclasses import asdict
from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd
import pytest

from src.core.random_benchmark import evaluate_random_benchmark
from src.services import strategy_lab_service as lab
from api.v1.endpoints import strategy_lab


@pytest.fixture()
def config():
    return SimpleNamespace(
        etf_rotation_pool=["510300", "518880", "AAPL"],
        etf_rotation_backtest_years=2,
        etf_rotation_lookback_days=15,
        etf_rotation_rebalance="weekly",
        etf_rotation_switch_buffer_pct=2,
        etf_rotation_cost_bps=10,
    )


def test_whitelist_is_explicit_and_normalized(config):
    assert lab.eligible_etfs(config) == ["510300", "518880"]
    with pytest.raises(ValueError, match="not in"):
        lab.analyze_configured_etf(asset_code="000001", config=config, fetcher_manager=Mock())
    with pytest.raises(ValueError, match="between"):
        lab.analyze_configured_etf(asset_code="510300", config=config, simulations=4001, fetcher_manager=Mock())


def test_service_uses_real_rotation_adapter_contract_but_no_side_effects(config, monkeypatch):
    dates = pd.bdate_range("2025-01-01", periods=50)
    frame = pd.DataFrame({"510300": [100.0 + i for i in range(50)]}, index=dates)
    loaded = SimpleNamespace(closes=frame, failed={}, sources={"510300": "EfinanceFetcher"})
    fetch = Mock(return_value=loaded)
    benchmark = evaluate_random_benchmark([100, 101, 99, 102], [0, 1, 0], simulations=100)
    adapter = Mock(return_value=benchmark)
    monkeypatch.setattr(lab, "load_closes", fetch)
    monkeypatch.setattr(lab, "data_quality_warnings", lambda _loaded: [])
    monkeypatch.setattr(lab, "evaluate_single_asset_rotation_history", adapter)
    result = lab.analyze_configured_etf(
        asset_code="510300", simulations=100, config=config, fetcher_manager=object(), end=dates[-1].date()
    )
    assert result["research_only"] is True
    assert result["asset_code"] == "510300"
    assert result["result"] == asdict(benchmark)
    assert result["history_start"] == "2025-01-01"
    assert result["data_source"] == "EfinanceFetcher"
    assert fetch.call_args.args[1] == ["510300"]
    assert fetch.call_args.args[2] == 2
    params = adapter.call_args.kwargs["params"]
    assert params.top_n == 1
    assert params.lookback_days == 15
    assert params.cost_bps == 10
    assert adapter.call_args.kwargs["simulations"] == 100


def test_unavailable_and_dirty_history_are_rejected(config, monkeypatch):
    idx = pd.bdate_range("2025-01-01", periods=50)
    frame = pd.DataFrame({"510300": [100.0 + i for i in range(50)]}, index=idx)
    monkeypatch.setattr(lab, "load_closes", lambda *_args, **_kwargs: SimpleNamespace(
        closes=frame, failed={}, sources={"510300": "test"},
    ))
    monkeypatch.setattr(lab, "data_quality_warnings", lambda _loaded: ["stale quote"])
    with pytest.raises(lab.BenchmarkDataUnavailable, match="quality"):
        lab.analyze_configured_etf(asset_code="510300", config=config, fetcher_manager=object(), end=idx[-1].date())

    monkeypatch.setattr(lab, "data_quality_warnings", lambda _loaded: [])
    monkeypatch.setattr(lab, "evaluate_single_asset_rotation_history", Mock(side_effect=ValueError("all-cash")))
    with pytest.raises(lab.BenchmarkDataUnavailable, match="Not enough"):
        lab.analyze_configured_etf(asset_code="510300", config=config, fetcher_manager=object(), end=idx[-1].date())


def test_endpoint_is_read_only_and_uses_configured_pool(config, monkeypatch):
    monkeypatch.setattr(strategy_lab, "get_config", lambda: config)
    assert strategy_lab.list_eligible_etfs() == {"items": ["510300", "518880"], "research_only": True}
    called = Mock(return_value={"research_only": True})
    monkeypatch.setattr(strategy_lab, "analyze_configured_etf", called)
    data = strategy_lab.evaluate_etf_timing(strategy_lab.EtfBenchmarkRequest(asset_code="510300", simulations=100))
    assert data["research_only"] is True
    assert called.call_args.kwargs["config"] is config
    assert called.call_args.kwargs["simulations"] == 100


def test_endpoint_rejects_invalid_inputs_and_provider_failures(config, monkeypatch):
    from fastapi import HTTPException
    from pydantic import ValidationError

    monkeypatch.setattr(strategy_lab, "get_config", lambda: config)
    with pytest.raises(ValidationError):
        strategy_lab.EtfBenchmarkRequest(asset_code="AAPL", simulations=100)
    with pytest.raises(ValidationError):
        strategy_lab.EtfBenchmarkRequest(asset_code="510300", simulations=99999)
    monkeypatch.setattr(strategy_lab, "analyze_configured_etf", Mock(side_effect=lab.BenchmarkDataUnavailable("no data")))
    with pytest.raises(HTTPException) as exc:
        strategy_lab.evaluate_etf_timing(strategy_lab.EtfBenchmarkRequest(asset_code="510300"))
    assert exc.value.status_code == 422
