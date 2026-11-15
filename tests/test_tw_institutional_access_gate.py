# -*- coding: utf-8 -*-
"""Offline contracts for opt-in TWSE/TPEx live-network schema probes.

The PR backend gate must never become dependent on a provider answering its
public OpenAPI endpoint. Real HTTP 200 feed shape drift still fails.
"""
from pathlib import Path
import unittest

import pytest

from tests import test_tw_institutional_network as live_probe


class _Response:
    def __init__(self, status_code: int, content=None):
        self.status_code = status_code
        self._content = content

    def json(self):
        if self._content is None:
            raise ValueError("non-JSON HTML challenge")
        return self._content


def _probe(monkeypatch, status_code: int, content=None):
    monkeypatch.setattr(
        live_probe.requests, "get",
        lambda *_args, **_kwargs: _Response(status_code, content),
    )
    case = live_probe.TestTwInstitutionalLiveNetwork()
    return case._get_feed_or_skip(live_probe._TPEX_URL)


@pytest.mark.parametrize("status", [401, 403, 408, 429, 500, 503])
def test_network_access_denied_is_skip_not_false_schema_drift(monkeypatch, status):
    with pytest.raises(unittest.SkipTest, match=f"HTTP {status}"):
        _probe(monkeypatch, status)


@pytest.mark.parametrize("status", [404, 410, 302])
def test_missing_or_redirected_endpoint_still_fails_loudly(monkeypatch, status):
    with pytest.raises(AssertionError, match=f"HTTP {status}"):
        _probe(monkeypatch, status)


def test_http_200_html_or_corrupted_json_still_fails_schema_probe(monkeypatch):
    with pytest.raises(AssertionError, match="returned non-JSON"):
        _probe(monkeypatch, 200)


def test_http_200_valid_json_proceeds_to_normal_shape_checks(monkeypatch):
    payload = [{"SecuritiesCompanyCode": "5483"}]
    assert _probe(monkeypatch, 200, content=payload) == payload


def test_pr_backend_gate_excludes_marked_network_but_retains_offline_tests():
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github" / "workflows" / "pr1-verify.yml").read_text(
        encoding="utf-8"
    )
    script = (root / "scripts" / "ci_gate.sh").read_text(encoding="utf-8")
    assert 'run: pytest -q -m "not network"' in workflow
    assert '-m "not network"' in script
    assert 'run: pytest -q\n' not in workflow
    assert "pytest.mark.network" in (
        root / "tests" / "test_tw_institutional_network.py"
    ).read_text(encoding="utf-8")
