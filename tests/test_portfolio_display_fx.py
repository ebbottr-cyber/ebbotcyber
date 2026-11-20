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

def test_additional_currencies_are_independently_converted_and_timestamped():
    now = datetime(2026, 11, 19, 9, 0, tzinfo=timezone.utc)
    result = build_try_display_rates(
        (50.0, now - timedelta(minutes=2)),
        (7.0, now - timedelta(minutes=3)),
        additional_quotes={
            "HKD": (8.0, now - timedelta(minutes=4)),
            "JPY": (160.0, now - timedelta(minutes=4)),
            "KRW": (1400.0, now - timedelta(minutes=5)),
            "TWD": (32.0, now - timedelta(minutes=5)),
        },
        now=now,
    )
    assert result["status"] == "current"
    for currency, expected in {"HKD": 6.25, "JPY": 0.3125, "KRW": 50 / 1400, "TWD": 1.5625}.items():
        assert abs(result[f"{currency.lower()}_try"] - expected) < 1e-7
        assert result["pair_status"][currency.lower()] == "current"
        assert result["pair_as_of"][currency.lower()]
    assert result["pair_status"]["usd"] == "current"


def test_bad_foreign_quote_cannot_poison_independent_valid_pair():
    now = datetime(2026, 11, 19, 9, 0, tzinfo=timezone.utc)
    result = build_try_display_rates(
        (50.0, now - timedelta(minutes=1)), None,
        additional_quotes={
            "HKD": (8.0, now - timedelta(minutes=2)),
            "JPY": (160.0, now - timedelta(minutes=29)),
            "KRW": (float("nan"), now),
        }, now=now,
    )
    assert result["status"] == "unavailable"
    assert result["pair_status"]["cny"] == "unavailable"
    assert result["pair_status"]["hkd"] == "current"
    assert result["hkd_try"] == 6.25
    assert result["pair_status"]["jpy"] == "stale"  # timestamps too far apart
    assert result["jpy_try"] is None and "jpy" not in result["pair_as_of"]
    assert result["pair_status"]["krw"] == "unavailable"
    assert result["krw_try"] is None and "krw" not in result["pair_as_of"]
    assert result["pair_status"]["twd"] == "unavailable"


def test_stale_usd_reference_invalidates_all_crosses():
    now = datetime(2026, 11, 19, 9, 0, tzinfo=timezone.utc)
    result = build_try_display_rates(
        (50.0, now - timedelta(hours=2)), (7.0, now),
        additional_quotes={"HKD": (8.0, now)}, now=now,
    )
    assert result["pair_status"]["usd"] == "stale"
    assert result["pair_status"]["hkd"] == "stale"
    assert result["hkd_try"] is None and result["cny_try"] is None


def test_wrong_unit_or_naive_pair_rejected_instead_of_guessing():
    now = datetime(2026, 11, 19, 9, 0, tzinfo=timezone.utc)
    result = build_try_display_rates(
        (50.0, now), (7.0, now),
        additional_quotes={"HKD": (8.0, now.replace(tzinfo=None)),
                           "JPY": (0.0, now),
                           "KRW": (float("inf"), now)},
        now=now,
    )
    for currency in ("HKD", "JPY", "KRW"):
        assert result["pair_status"][currency.lower()] == "unavailable"
        assert result[f"{currency.lower()}_try"] is None
