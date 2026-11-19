"""Ensure archived workflows never silently become scheduled jobs."""
from pathlib import Path

from tests.workflow_archive_contract import ARCHIVED_NAMES, archived_workflow


def test_archived_workflows_remain_inactive_but_verifiable():
    root = Path(__file__).resolve().parents[1]
    for name in sorted(ARCHIVED_NAMES):
        assert archived_workflow(root, name).suffix == ".disabled"
