from __future__ import annotations

from shared.taskflow_common import burndown_series, estimate_completion_days, mape


def test_mape_target() -> None:
    actual = [10, 12, 11, 13]
    predicted = [9, 11, 12, 12]
    score = mape(actual, predicted)
    assert score < 15


def test_estimation_has_confidence() -> None:
    days, confidence = estimate_completion_days([3, 4, 5, 4, 3], remaining_points=20)
    assert days > 0
    assert 0 <= confidence <= 1


def test_burndown_shape() -> None:
    points = burndown_series(total_scope=20, actual_burn=[2, 4, 3, 5])
    assert len(points) == 4
    assert points[0].planned_remaining > points[-1].planned_remaining
