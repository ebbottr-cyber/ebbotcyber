"""Chronological research validation: no future leakage, no silent skips."""
import math

import numpy as np
import pandas as pd
import pytest

from src.core.etf_rotation import RotationParams
from src.core.temporal_validation import evaluate_temporal_holdout


def _history(count=320, variant="mixed"):
    dates = pd.bdate_range("2024-01-02", periods=count)
    if variant == "rising":
        daily = np.full(count, 1.003)
    elif variant == "falling":
        daily = np.full(count, 0.997)
    else:
        daily = np.array([
            1.014 if ((i // 18) % 2 == 0) else 0.987
            for i in range(count)
        ])
    return pd.DataFrame({"510300": 100 * np.cumprod(daily)}, index=dates)


def _run(frame=None, **options):
    return evaluate_temporal_holdout(
        _history() if frame is None else frame,
        asset_code="510300",
        params=RotationParams(lookback_days=12, rebalance="weekly", cost_bps=10),
        min_training_intervals=140,
        walk_forward_folds=3,
        min_fold_intervals=20,
        holdout_fraction=0.2,
        simulations=100,
        seed=42,
        **options,
    )


def test_chronology_boundaries_are_nonoverlapping_and_holdout_is_last():
    report = _run()
    windows = report.windows
    assert len(windows) == 4
    assert report.fold_count == 3
    assert report.mode == "expanding_history_fixed_parameters"
    assert report.training_policy == "no_optimization"
    assert [w.label for w in windows] == ["fold_1", "fold_2", "fold_3", "final_holdout"]
    assert [w.kind for w in windows] == ["walk_forward"] * 3 + ["holdout"]
    for before, after in zip(windows, windows[1:]):
        assert before.test_end_close == after.test_start_close
        assert before.training_end < before.test_end_close
    assert windows[-1].test_end_close == _history().index[-1].date().isoformat()
    assert sum(w.test_intervals for w in windows) == len(_history()) - 1 - 140
    assert report.split_index > 140
    assert report.holdout_status in {"EVALUATED", "NONINFORMATIVE", "NO_LONG_EXPOSURE"}


def test_seeding_keeps_all_outcomes_reproducible():
    a = _run()
    b = _run()
    assert a == b


def test_holdout_prices_cannot_change_any_prior_fold_report():
    frame = _history()
    before = _run(frame)
    changed = frame.copy()
    cutoff = before.split_index
    # Future data is altered only AFTER the last training/OOS walk-forward close.
    changed.iloc[cutoff + 1:, 0] *= np.linspace(1.02, 0.41, len(changed) - cutoff - 1)
    after = _run(changed)
    assert before.windows[:3] == after.windows[:3]
    assert before.windows[-1].test_end_close == after.windows[-1].test_end_close


def test_changing_later_fold_does_not_change_first_fold():
    frame = _history()
    before = _run(frame)
    first_end = int(frame.index.get_loc(pd.Timestamp(before.windows[0].test_end_close)))
    changed = frame.copy()
    changed.iloc[first_end + 1:, 0] *= 0.75
    after = _run(changed)
    assert before.windows[0] == after.windows[0]


def test_cash_only_is_reported_and_never_given_false_random_ranking():
    frame = _history(320, variant="falling")
    report = _run(frame)
    assert report.evaluated_folds == 0
    assert all(w.status == "NO_LONG_EXPOSURE" and w.benchmark is None for w in report.windows)


def test_all_long_boundary_is_explicitly_noninformative_not_strong_edge():
    frame = _history(320, variant="rising")
    report = _run(frame)
    assert all(w.benchmark is not None for w in report.windows)
    assert all(w.status == "NONINFORMATIVE" for w in report.windows)
    assert all(w.benchmark.entry_count == 1 for w in report.windows)
    assert all(w.benchmark.distinct_random_schedules == 1 for w in report.windows)
    assert report.evaluated_folds == 0


def test_fold_results_are_independent_and_costed_with_boundary_liquidation():
    frame = _history(320, variant="rising")
    a = _run(frame)
    higher_fee = evaluate_temporal_holdout(
        frame, asset_code="510300",
        params=RotationParams(lookback_days=12, cost_bps=100),
        min_training_intervals=140, simulations=100,
    )
    assert a.windows[-1].benchmark is not None
    assert higher_fee.windows[-1].benchmark is not None
    assert higher_fee.windows[-1].benchmark.observed_return_pct < a.windows[-1].benchmark.observed_return_pct


def test_holdout_guardrails_reject_bad_splits_and_nonpositive_prices():
    valid = _history()
    with pytest.raises(ValueError, match="insufficient data"):
        _run(valid.iloc[:220])
    for bad_params in (
        {"min_training_intervals": 3},
        {"holdout_fraction": 0.8},
        {"walk_forward_folds": 0},
        {"min_fold_intervals": 1},
        {"simulations": 10001},
    ):
        # Avoid duplicate-key parameters in _run helper: call directly.
        with pytest.raises(ValueError):
            evaluate_temporal_holdout(
                valid, asset_code="510300",
                params=RotationParams(lookback_days=12),
                **bad_params,
            )
    wrong = valid.copy()
    wrong.iloc[15, 0] = np.nan
    with pytest.raises(ValueError, match="finite"):
        _run(wrong)
    dup = valid.copy()
    duplicated_dates = list(dup.index)
    duplicated_dates[1] = duplicated_dates[0]
    dup.index = pd.DatetimeIndex(duplicated_dates)
    with pytest.raises(ValueError, match="unique"):
        _run(dup)
    with pytest.raises(ValueError, match="single-column"):
        _run(valid.assign(other=1.0))
    with pytest.raises(ValueError, match="single-asset"):
        evaluate_temporal_holdout(
            valid, asset_code="510300", params=RotationParams(top_n=2),
        )
