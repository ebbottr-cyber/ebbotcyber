"""Protect copied public env template from accidental live automation or secrets."""

from pathlib import Path


def _active():
    content = (Path(__file__).resolve().parents[1] / ".env.example").read_text(encoding="utf-8")
    return dict(line.strip().split("=", 1) for line in content.splitlines()
                if line.strip() and not line.lstrip().startswith("#") and "=" in line)


def test_template_defaults_do_not_activate_schedules_or_live_trading():
    keys = _active()
    for setting in ("SCHEDULE_ENABLED", "MEME_RADAR_LIVE_ENABLED", "AUTO_TRADING_ENABLED"):
        assert keys.get(setting, "false").lower() not in ("true", "1", "yes", "on")
    assert keys.get("SEARXNG_PUBLIC_INSTANCES_ENABLED") == "false"
    assert keys.get("SEARXNG_TIMEOUT_SECONDS") == "10"


def test_template_contains_no_active_credentials():
    for key, value in _active().items():
        if key.endswith(("_API_KEY", "_API_KEYS", "_TOKEN", "_SECRET", "_PASSWORD")):
            assert not value, f"Do not commit values for {key}"
