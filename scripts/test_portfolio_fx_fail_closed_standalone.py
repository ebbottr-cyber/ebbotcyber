# -*- coding: utf-8 -*-
"""Dependency-light guards against invented portfolio FX valuations.

Extract and execute the *actual* backend methods from their source AST rather
than duplicating conversion/risk logic in these tests. This suite needs only
pytest + Python stdlib and is safe to run without market data or credentials.
"""
from __future__ import annotations

import ast
import math
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]


def _compile_method(filename: str, class_name: str, method: str, namespace: dict):
    tree = ast.parse((ROOT / filename).read_text(encoding="utf-8"))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name)
    fn = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == method)
    # Resolve only the function's real code, without importing database/market
    # dependencies into the isolated regression runner.
    exec(compile(ast.Module(body=[fn], type_ignores=[]), filename, "exec"), namespace)
    return namespace[method]


def _fx_components():
    ns = {"date": date, "math": math, "Tuple": Tuple, "EPS": 1e-8}
    module = ast.parse((ROOT / "src/services/portfolio_service.py").read_text(encoding="utf-8"))
    cls = next(node for node in module.body if isinstance(node, ast.ClassDef) and node.name == "PortfolioFxRateUnavailableError")
    exec(compile(ast.Module(body=[cls], type_ignores=[]), "portfolio_service.py", "exec"), ns)
    method = _compile_method("src/services/portfolio_service.py", "PortfolioService", "_convert_amount", ns)
    return method, ns["PortfolioFxRateUnavailableError"]


def _fake_fx_service(direct=None, inverse=None):
    method, error = _fx_components()
    calls = []

    class Repo:
        def get_latest_fx_rate(self, *, from_currency, to_currency, as_of):
            calls.append((from_currency, to_currency))
            return direct if (from_currency, to_currency) == ("USD", "CNY") else inverse

    service = SimpleNamespace(
        repo=Repo(),
        _normalize_currency=lambda value: value.strip().upper(),
    )
    return lambda amount, src="USD", dst="CNY": method(
        service,
        amount=amount,
        from_currency=src,
        to_currency=dst,
        as_of_date=date(2026, 11, 20),
    ), error, calls


def test_missing_rate_raises_instead_of_faking_1_to_1():
    converter, error, calls = _fake_fx_service()
    try:
        converter(250)
    except error as exc:
        assert exc.from_currency == "USD"
        assert exc.to_currency == "CNY"
        assert "not calculated" in str(exc)
    else:
        raise AssertionError("Nonzero USD/CNY converted without an FX rate")
    assert calls == [("USD", "CNY"), ("CNY", "USD")]


def test_zero_and_identity_need_no_conversion_quote():
    converter, _, calls = _fake_fx_service()
    assert converter(0) == (0.0, False, "zero")
    assert converter(17, "CNY", "CNY") == (17, False, "identity")
    assert calls == []


def test_valid_direct_inverse_and_stale_rates_are_explicit():
    direct = SimpleNamespace(rate=7.0, is_stale=False)
    converter, _, _ = _fake_fx_service(direct=direct)
    assert converter(10) == (70.0, False, "direct_rate")
    stale = SimpleNamespace(rate=0.14, is_stale=True)
    converter, _, _ = _fake_fx_service(inverse=stale)
    actual, flagged, kind = converter(7)
    assert abs(actual - 50) < 1e-9
    assert flagged is True and kind == "inverse_rate"


def test_invalid_nan_rate_does_not_create_a_portfolio_amount():
    converter, error, _ = _fake_fx_service(direct=SimpleNamespace(rate=float("nan"), is_stale=False))
    try:
        converter(25)
    except error:
        pass
    else:
        raise AssertionError("Invalid NaN rate was accepted")


def _risk_method(name):
    namespace = {
        "date": date, "math": math, "Tuple": Tuple, "List": List,
        "Dict": Dict, "Any": Any, "Optional": Optional,
    }
    return _compile_method("src/services/portfolio_risk_service.py", "PortfolioRiskService", name, namespace)


def test_stale_fx_suppresses_concentration_and_sector_percentages():
    snapshot = {
        "fx_stale": True,
        "total_market_value": 1800,
        "accounts": [{
            "fx_stale": True,
            "positions": [{"symbol": "AAPL", "market_value_base": 100, "valuation_currency": "USD"}],
        }],
    }
    for name in ("_build_concentration", "_build_sector_concentration"):
        method = _risk_method(name)
        block = method(SimpleNamespace(), snapshot, 30.0, as_of_date=date(2026, 11, 20))
        assert block["available"] is False
        assert block["fx_stale"] is True
        assert block["top_weight_pct"] is None
        assert block["alert"] is None
        assert block["total_market_value"] is None
        assert block["top_positions" if name == "_build_concentration" else "top_sectors"] == []


def test_historical_drawdown_is_unavailable_if_any_rate_is_stale():
    method = _risk_method("_build_drawdown")
    historical = SimpleNamespace(
        snapshot_date=date(2026, 11, 19), total_equity=100, base_currency="USD", fx_stale=True,
    )
    repo = SimpleNamespace(list_daily_snapshots_for_risk=lambda **kwargs: [historical])
    service = SimpleNamespace(convert_amount=lambda **kwargs: (700.0, True, "direct_rate"))
    risk = SimpleNamespace(repo=repo, portfolio_service=service)
    block = method(risk, account_id=1, as_of_date=date(2026, 11, 20),
                   cost_method="fifo", threshold_pct=10, lookback_days=180)
    assert block["fx_stale"] is True
    assert block["series_points"] == 1
    assert block["max_drawdown_pct"] is None
    assert block["current_drawdown_pct"] is None
    assert block["alert"] is None


def test_snapshot_and_risk_endpoints_handle_rate_unavailable_as_503():
    source = (ROOT / "api/v1/endpoints/portfolio.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for name in ("get_snapshot", "get_risk_report", "analyze_position"):
        fn = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)
        handlers = [node.type.id for node in ast.walk(fn) if isinstance(node, ast.ExceptHandler)
                    and isinstance(node.type, ast.Name)]
        assert "PortfolioFxRateUnavailableError" in handlers
    assert 'api_error(503, "portfolio_fx_rate_unavailable"' in source
