"""Guardrail: contract tests may inspect archived workflows, never activate them."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
ARCHIVED = (
    "00-daily-analysis.yml",
    "ci.yml",
    "docker-publish.yml",
    "ghcr-dockerhub.yml",
)


def test_archived_automation_sources_stay_outside_active_workflows():
    for filename in ARCHIVED:
        assert (ROOT / "workflows_disabled" / (filename + ".disabled")).is_file()
        assert not (ROOT / ".github" / "workflows" / filename).exists()


def test_active_pr_verification_has_no_scheduled_trading_jobs():
    active = ROOT / ".github" / "workflows"
    for workflow in active.glob("*.yml"):
        data = yaml.load(workflow.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
        events = data.get("on", {}) if isinstance(data, dict) else {}
        assert "schedule" not in events, f"Scheduled workflow must be reviewed explicitly: {workflow.name}"
