from datetime import datetime, timedelta, timezone

from src.services.portfolio_display_fx import build_try_display_rates


def test_cross_rate_uses_both_dollar_quotes():
    now = datetime(2026, 11, 19, 9, 0, tzinfo=timezone.utc)
    result = build_try_display_rates(
        (50.0, now - timedelta(minutes=2)),
        (7.0, now - timedelta(minutes=3)),
        now=now,
    )
    assert result["status"] == "current"
    assert abs(result["cny_try"] - 50 / 7) < 1e-7
    assert result["usd_try"] == 50
    assert result["usd_cny"] == 7


def test_missing_or_invalid_rate_does_not_produce_a_fake_try_value():
    now = datetime(2026, 11, 19, 9, 0, tzinfo=timezone.utc)
    for missing in (None, (0, now), (-2, now), (float("nan"), now)):
        result = build_try_display_rates((50, now), missing, now=now)
        assert result["status"] == "unavailable"
        assert result["cny_try"] is None


def test_stale_and_mismatched_timestamps_rejected():
    now = datetime(2026, 11, 19, 9, 0, tzinfo=timezone.utc)
    stale = build_try_display_rates((50, now - timedelta(hours=2)), (7, now), now=now)
    mismatch = build_try_display_rates(
        (50, now - timedelta(minutes=2)),
        (7, now - timedelta(minutes=25)),
        now=now,
    )
    assert stale["status"] == "stale"
    assert mismatch["status"] == "stale"
    assert stale["cny_try"] is None and mismatch["cny_try"] is None


def test_naive_timestamp_does_not_get_assumed_utc():
    now = datetime(2026, 11, 19, 9, 0, tzinfo=timezone.utc)
    result = build_try_display_rates((50, now), (7, now.replace(tzinfo=None)), now=now)
    assert result["status"] == "unavailable"
    assert result["cny_try"] is None
