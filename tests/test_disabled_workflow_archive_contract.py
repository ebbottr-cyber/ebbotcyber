"""Archive should remain inspectable for contract tests but never active."""
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
DISABLED = ROOT / "workflows_disabled"
ACTIVE = ROOT / ".github" / "workflows"


def test_original_workflows_live_only_in_disabled_archive():
    for base in ("00-daily-analysis", "ci", "docker-publish", "ghcr-dockerhub"):
        snapshot = DISABLED / f"{base}.yml.disabled"
        assert snapshot.is_file(), f"missing archived contract: {snapshot}"
        assert (ACTIVE / f"{base}.yml").exists() is False
        parsed = yaml.load(snapshot.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
        assert isinstance(parsed, dict) and isinstance(parsed.get("jobs"), dict)


def test_active_workflow_directory_does_not_schedule_daily_analysis():
    for path in ACTIVE.glob("*.yml"):
        text = path.read_text(encoding="utf-8")
        parsed = yaml.load(text, Loader=yaml.BaseLoader)
        if not isinstance(parsed, dict):
            continue
        # BaseLoader keeps the "on" trigger as a string key.
        trigger = parsed.get("on")
        if isinstance(trigger, dict):
            assert "schedule" not in trigger, f"unexpected active schedule: {path}"
        assert not path.name.startswith("00-daily-analysis")


def test_recovered_example_env_contains_no_real_keys_and_disables_public_searxng():
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "SEARXNG_PUBLIC_INSTANCES_ENABLED=false" in example
    active = [line.strip() for line in example.splitlines()
              if line.strip() and not line.lstrip().startswith("#") and "=" in line]
    assert all(not key.endswith(("_API_KEY", "_TOKEN", "_SECRET", "_PASSWORD"))
               or not value for key, value in (line.split("=", 1) for line in active))
    assert not any(line.startswith(("LLM_CHANNELS=", "MEME_COIN_DISCOVERY_ENABLED=true"))
                   for line in active)
