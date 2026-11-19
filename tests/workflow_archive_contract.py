"""Read archived, inactive GitHub workflow contracts without activating them.

These tests preserve and verify archived workflow metadata only; they do NOT
claim the archived workflows are running in current CI.
"""

from __future__ import annotations

from pathlib import Path


ARCHIVED_NAMES = frozenset({
    "ci.yml",
    "00-daily-analysis.yml",
    "docker-publish.yml",
    "ghcr-dockerhub.yml",
})


def archived_workflow(root: Path, name: str) -> Path:
    if name not in ARCHIVED_NAMES:
        raise ValueError(f"Not an approved archived workflow: {name}")
    active = root / ".github" / "workflows" / name
    archive = root / "workflows_disabled" / f"{name}.disabled"
    assert not active.exists(), f"Archived workflow unexpectedly active: {name}"
    assert archive.is_file(), f"Archived workflow snapshot is missing: {archive}"
    return archive
