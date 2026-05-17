from __future__ import annotations

from collections import Counter
from datetime import date

from .schemas import BurnoutSignal, RiskLevel, TaskPriority


def recommend_assignee(
    task_tags: list[str],
    candidates: list[dict],
    due_date: date | None = None,
) -> dict | None:
    if not candidates:
        return None
    tags = Counter(task_tags)
    best = None
    best_score = -1.0
    for candidate in candidates:
        user_id = candidate.get("user_id")
        skills = candidate.get("skills", [])
        free_hours = float(candidate.get("free_hours_week", 0))
        quality = float(candidate.get("quality_score", 0.7))
        capacity_score = min(1.0, free_hours / 20.0)
        skill_score = sum(tags.get(skill, 0) for skill in skills) * 0.15
        deadline_bonus = 0.05 if due_date else 0.0
        total = quality * 0.5 + capacity_score * 0.35 + skill_score + deadline_bonus
        if total > best_score:
            best_score = total
            best = {"user_id": user_id, "score": round(min(1.0, total), 2), "reason": "skills+capacity+quality"}
    return best


def estimate_task_days(priority: TaskPriority, complexity: float, historical_cycle_days: list[float]) -> float:
    baseline = sum(historical_cycle_days) / len(historical_cycle_days) if historical_cycle_days else 3.0
    factor = {
        TaskPriority.LOW: 0.9,
        TaskPriority.MEDIUM: 1.0,
        TaskPriority.HIGH: 1.15,
        TaskPriority.CRITICAL: 1.3,
    }[priority]
    estimate = baseline * factor * max(0.5, complexity)
    return round(estimate, 2)


def burnout_risk(
    user_id: str,
    booked_hours_week: float,
    capacity_hours_week: float,
    night_activity_ratio: float,
    context_switches: int,
) -> BurnoutSignal:
    overload = booked_hours_week / max(capacity_hours_week, 1.0)
    score = min(1.0, overload * 0.5 + night_activity_ratio * 0.3 + min(context_switches / 50.0, 1.0) * 0.2)
    if score >= 0.85:
        level = RiskLevel.CRITICAL
    elif score >= 0.65:
        level = RiskLevel.HIGH
    elif score >= 0.4:
        level = RiskLevel.MEDIUM
    else:
        level = RiskLevel.LOW
    return BurnoutSignal(
        user_id=user_id,
        overload_ratio=round(overload, 2),
        night_activity_ratio=round(night_activity_ratio, 2),
        context_switches=context_switches,
        risk_score=round(score, 2),
        level=level,
    )
