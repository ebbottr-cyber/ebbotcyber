# -*- coding: utf-8 -*-
"""Publishing a saved ranking must remain explicit, atomic and offline."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import stat

import pytest

from src.services.bist100_report_publisher import (
    ReportPublicationError,
    prepare_saved_report,
)
from src.services.bist100_technical_report_reader import load_configured_technical_report
from tests.test_bist100_technical_report_reader import _report


def _source(
    tmp_path: Path, report=None, *, name: str = "incoming-real-shaped-report.json"
) -> tuple[Path, str]:
    path = tmp_path / name
    payload = _report() if report is None else report
    data = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
    path.write_bytes(data)
    return path, hashlib.sha256(data).hexdigest()


def test_preview_does_not_need_server_path_or_write_any_files(monkeypatch, tmp_path):
    monkeypatch.delenv("BIST100_TECHNICAL_REPORT_PATH", raising=False)
    path, digest = _source(tmp_path)
    before = {p.name for p in tmp_path.iterdir()}
    response = prepare_saved_report(path)
    assert response == {
        "mode": "validated_preview",
        "sha256": digest,
        "as_of": "2026-11-15",
        "last_completed_session": "2026-11-13",
        "checked": 2,
        "analyzed": 1,
        "remaining": 98,
        "watchlist_eligible": 1,
    }
    assert {p.name for p in tmp_path.iterdir()} == before


def test_atomic_publish_updates_exact_configured_report_and_reader(monkeypatch, tmp_path):
    source, digest = _source(tmp_path)
    target = tmp_path / "approved" / "technical.json"
    target.parent.mkdir()
    monkeypatch.setenv("BIST100_TECHNICAL_REPORT_PATH", str(target))
    with pytest.raises(ReportPublicationError, match="requires an explicit expected"):
        prepare_saved_report(source, publish=True)
    published = prepare_saved_report(source, expected_sha256=digest, publish=True)
    assert published["mode"] == "published"
    assert published["sha256"] == digest
    assert target.read_bytes() == source.read_bytes()
    assert load_configured_technical_report()["checked"] == 2
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert not any(target.parent.glob("*.tmp"))
    assert not any(target.parent.glob(".technical.json.*"))


def test_publish_will_not_overwrite_without_explicit_replace(monkeypatch, tmp_path):
    source, digest = _source(tmp_path)
    target = tmp_path / "saved.json"
    target.write_text("old report", encoding="utf-8")
    monkeypatch.setenv("BIST100_TECHNICAL_REPORT_PATH", str(target))
    with pytest.raises(ReportPublicationError, match="replace-existing"):
        prepare_saved_report(source, publish=True, expected_sha256=digest)
    assert target.read_text(encoding="utf-8") == "old report"
    result = prepare_saved_report(source, publish=True, expected_sha256=digest,
                                  replace_existing=True)
    assert result["mode"] == "published"
    assert target.read_bytes() == source.read_bytes()


def test_wrong_digest_and_unverified_report_cannot_publish(monkeypatch, tmp_path):
    source, digest = _source(tmp_path)
    target = tmp_path / "approved.json"
    monkeypatch.setenv("BIST100_TECHNICAL_REPORT_PATH", str(target))
    with pytest.raises(ReportPublicationError, match="SHA-256"):
        prepare_saved_report(source, expected_sha256="f" * 64, publish=True)
    assert not target.exists()

    wrong = deepcopy(_report())
    wrong["checked"] = 100
    bad, bad_digest = _source(tmp_path, wrong)
    with pytest.raises(ReportPublicationError, match="validation"):
        prepare_saved_report(bad, expected_sha256=bad_digest, publish=True)
    assert not target.exists()
    assert digest != bad_digest


def test_stale_xist_session_cannot_publish_even_when_rank_rows_agree(monkeypatch, tmp_path):
    wrong = deepcopy(_report())
    wrong["last_completed_session"] = "2026-11-12"
    wrong["ranking"][0]["last_bar_date"] = "2026-11-12"
    wrong["results"][0]["last_bar_date"] = "2026-11-12"
    source, digest = _source(tmp_path, wrong)
    target = tmp_path / "saved.json"
    monkeypatch.setenv("BIST100_TECHNICAL_REPORT_PATH", str(target))
    with pytest.raises(ReportPublicationError, match="validation"):
        prepare_saved_report(source, publish=True, expected_sha256=digest)
    assert not target.exists()


@pytest.mark.parametrize("configured", [
    "", "relative/technical.json", "/some/irrelevant/file.txt",
])
def test_unsafe_or_missing_destination_fails_closed(monkeypatch, tmp_path, configured):
    source, digest = _source(tmp_path)
    monkeypatch.setenv("BIST100_TECHNICAL_REPORT_PATH", configured)
    with pytest.raises(ReportPublicationError):
        prepare_saved_report(source, publish=True, expected_sha256=digest)


def test_reject_symlink_destination_and_symlink_source(monkeypatch, tmp_path):
    source, digest = _source(tmp_path)
    private = tmp_path / "unrelated-data.json"
    private.write_text("do not overwrite", encoding="utf-8")
    target = tmp_path / "technical.json"
    target.symlink_to(private)
    monkeypatch.setenv("BIST100_TECHNICAL_REPORT_PATH", str(target))
    with pytest.raises(ReportPublicationError, match="symlink"):
        prepare_saved_report(source, publish=True, expected_sha256=digest,
                             replace_existing=True)
    assert private.read_text(encoding="utf-8") == "do not overwrite"
    alias = tmp_path / "alias.json"
    alias.symlink_to(source)
    with pytest.raises(ReportPublicationError, match="Source"):
        prepare_saved_report(alias)


def test_source_cannot_be_republished_to_itself(monkeypatch, tmp_path):
    source, digest = _source(tmp_path)
    monkeypatch.setenv("BIST100_TECHNICAL_REPORT_PATH", str(source))
    with pytest.raises(ReportPublicationError, match="must differ"):
        prepare_saved_report(source, expected_sha256=digest, publish=True,
                             replace_existing=True)
    assert source.read_bytes()


def test_invalid_digest_and_large_json_do_not_write_to_disk(monkeypatch, tmp_path):
    source, _ = _source(tmp_path)
    monkeypatch.setenv("BIST100_TECHNICAL_REPORT_PATH", str(tmp_path / "technical.json"))
    with pytest.raises(ReportPublicationError, match="64"):
        prepare_saved_report(source, publish=True, expected_sha256="zz")
    source.write_bytes(b"x" * 2_000_001)
    with pytest.raises(ReportPublicationError, match="2 MB"):
        prepare_saved_report(source, publish=True, expected_sha256="0" * 64)
    assert not (tmp_path / "technical.json").exists()


def test_nonexistent_output_directory_does_not_get_created(monkeypatch, tmp_path):
    source, digest = _source(tmp_path)
    target = tmp_path / "production-unknown" / "technical.json"
    monkeypatch.setenv("BIST100_TECHNICAL_REPORT_PATH", str(target))
    with pytest.raises(ReportPublicationError, match="parent"):
        prepare_saved_report(source, publish=True, expected_sha256=digest)
    assert not target.parent.exists()


def test_failed_validation_leaves_approved_existing_report_unchanged(monkeypatch, tmp_path):
    existing, digest = _source(tmp_path)
    approved = tmp_path / "approved.json"
    approved.write_bytes(existing.read_bytes())
    monkeypatch.setenv("BIST100_TECHNICAL_REPORT_PATH", str(approved))
    wrong = deepcopy(_report())
    wrong["analyzed"] = 99
    bad, bad_digest = _source(tmp_path, wrong, name="invalid-candidate.json")
    with pytest.raises(ReportPublicationError, match="validation"):
        prepare_saved_report(bad, publish=True, expected_sha256=bad_digest,
                             replace_existing=True)
    assert approved.read_bytes() == existing.read_bytes()
    assert digest == hashlib.sha256(approved.read_bytes()).hexdigest()
