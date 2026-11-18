# -*- coding: utf-8 -*-
"""Historical Futu distribution contracts; archived workflows cannot run."""

from __future__ import annotations

from pathlib import Path
import re

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def _workflow(relative_path: str) -> dict:
    return yaml.load(_read(relative_path), Loader=yaml.BaseLoader)


def _job_run_text(job: dict) -> str:
    return "\n".join(
        str(step.get("run", ""))
        for step in job.get("steps", [])
        if isinstance(step, dict)
    )


def test_archived_futu_sdk_is_pinned_and_verified_across_linux_distributions() -> None:
    requirements = _read("requirements.txt")
    dockerfile = _read("docker/Dockerfile")
    ci = _workflow("workflows_disabled/ci.yml.disabled")
    daily = _workflow("workflows_disabled/00-daily-analysis.yml.disabled")
    docker_publish = _workflow("workflows_disabled/docker-publish.yml.disabled")
    manual_publish = _workflow("workflows_disabled/ghcr-dockerhub.yml.disabled")

    assert requirements.count("futu-api==10.8.6808") == 1
    assert (
        'python -c "import src.services.screening.pipeline; import futu"'
        in dockerfile
    )
    assert "import futu" in _job_run_text(ci["jobs"]["backend-tests"])
    assert "import futu" in _job_run_text(ci["jobs"]["docker-build"])
    assert "import futu" in _job_run_text(daily["jobs"]["analyze"])
    assert "import futu" in _job_run_text(docker_publish["jobs"]["build-and-push"])
    assert "import futu" in _job_run_text(manual_publish["jobs"]["build-and-push"])


def test_archived_futu_sdk_is_collected_and_probed_in_desktop_backends() -> None:
    ci = _workflow("workflows_disabled/ci.yml.disabled")
    changes_job = ci["jobs"]["changes"]
    filter_step = next(
        step for step in changes_job["steps"] if step.get("id") == "filter"
    )
    filters = str(filter_step["with"]["filters"])
    jobs = ci["jobs"]
    macos_script = _read("scripts/build-backend-macos.sh")
    windows_script = _read("scripts/build-backend.ps1")

    assert "futu_packaging:" in filters
    assert "requirements.txt" in filters
    assert "src/brokers/futu/**" in filters
    assert "scripts/build-backend-macos.sh" in filters
    assert "scripts/build-backend.ps1" in filters

    for job_name in (
        "desktop-futu-package-windows",
        "desktop-futu-package-macos",
    ):
        job = jobs[job_name]
        assert job["needs"] == ["changes", "ai-governance"]
        assert "needs.changes.outputs.futu_packaging == 'true'" in job["if"]
        assert "build-backend" in _job_run_text(job)

    assert '"${PYTHON_BIN}" -c "import futu"' in macos_script
    assert 'cmd+=("--collect-all" "futu")' in macos_script
    assert "for module in src.services.screening.pipeline futu orjson" in macos_script

    assert 'Test-PythonCode -Python $pythonBin -Code "import futu"' in windows_script
    assert "'--collect-all', 'futu'" in windows_script
    probe = re.search(r"foreach \(\$module in @\(([^)]*)\)\)", windows_script)
    assert probe is not None
    probe_modules = set(re.findall(r"'([^']+)'", probe.group(1)))
    assert {"src.services.screening.pipeline", "futu", "orjson"} <= probe_modules


def test_current_integration_does_not_enable_futu_distribution_or_scheduled_analysis() -> None:
    active = _workflow(".github/workflows/ebbot-integration.yml")
    assert "schedule" not in active["on"]
    assert "workflow_dispatch" not in active["on"]
    assert active["permissions"] == {"contents": "read"}
    assert "full-backend-regression" in active["jobs"]
    assert not any(
        name in active["jobs"] for name in (
            "docker-build", "desktop-futu-package-windows",
            "desktop-futu-package-macos", "build-and-push",
        )
    )
    assert not (REPO_ROOT / ".github/workflows/00-daily-analysis.yml").exists()
