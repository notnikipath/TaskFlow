from __future__ import annotations

from math import sqrt

from .schemas import BurndownPoint, ForecastResult


def mape(actual: list[float], predicted: list[float]) -> float:
    if not actual or not predicted:
        return 0.0
    size = min(len(actual), len(predicted))
    errors = []
    for idx in range(size):
        if actual[idx] == 0:
            continue
        errors.append(abs((actual[idx] - predicted[idx]) / actual[idx]))
    if not errors:
        return 0.0
    return round((sum(errors) / len(errors)) * 100, 2)


def estimate_completion_days(history: list[float], remaining_points: float) -> tuple[int, float]:
    """
    Estimate duration based on velocity with confidence by variability.
    """
    if not history:
        return int(max(1, round(remaining_points))), 0.2
    velocity = sum(history) / len(history)
    if velocity <= 0:
        return int(max(1, round(remaining_points))), 0.1
    variance = 0.0
    if len(history) > 1:
        mu = velocity
        variance = sum((value - mu) ** 2 for value in history) / (len(history) - 1)
    std = sqrt(variance)
    days = int(max(1, round(remaining_points / velocity)))
    confidence = max(0.2, min(0.95, 1.0 - (std / max(velocity, 1.0))))
    return days, round(confidence, 2)


def forecast_completion(project_id: str, completed_points_history: list[float], target_points: float) -> ForecastResult:
    done = sum(completed_points_history)
    remaining = max(0.0, target_points - done)
    days, confidence = estimate_completion_days(completed_points_history, remaining)
    return ForecastResult(project_id=project_id, predicted_days_to_complete=days, confidence=confidence)


def burndown_series(total_scope: float, actual_burn: list[float]) -> list[BurndownPoint]:
    if total_scope <= 0:
        return []
    total_days = max(len(actual_burn), 1)
    planned_daily = total_scope / total_days

    series: list[BurndownPoint] = []
    planned_remaining = total_scope
    actual_remaining = total_scope

    for day in range(total_days):
        planned_remaining = max(0.0, planned_remaining - planned_daily)
        actual_remaining = max(0.0, actual_remaining - actual_burn[day])
        series.append(
            BurndownPoint(
                day=day + 1,
                planned_remaining=round(planned_remaining, 2),
                actual_remaining=round(actual_remaining, 2),
            )
        )
    return series


def gantt_parallel_hint(tasks: list[dict]) -> dict:
    """
    Optional improvement: parallel gantt calculation hint.
    Returns execution plan for chunked processing.
    """
    chunks = {}
    for item in tasks:
        project_id = str(item.get("project_id", "unknown"))
        chunks.setdefault(project_id, 0)
        chunks[project_id] += 1
    workers = min(16, max(1, len(chunks)))
    return {"projects": len(chunks), "workers": workers, "chunk_sizes": chunks}
