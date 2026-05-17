from __future__ import annotations

from datetime import date

from shared.taskflow_common import RiskLevel, TaskPriority, burnout_risk, estimate_task_days, recommend_assignee


def test_assignee_recommendation() -> None:
    result = recommend_assignee(
        task_tags=["backend", "api", "backend"],
        due_date=date.today(),
        candidates=[
            {"user_id": "USR-1", "skills": ["backend", "api"], "free_hours_week": 12, "quality_score": 0.8},
            {"user_id": "USR-2", "skills": ["design"], "free_hours_week": 18, "quality_score": 0.9},
        ],
    )
    assert result is not None
    assert result["user_id"] == "USR-1"


def test_task_estimation() -> None:
    value = estimate_task_days(TaskPriority.HIGH, complexity=1.2, historical_cycle_days=[2, 3, 4])
    assert value >= 2


def test_burnout_signal_level() -> None:
    signal = burnout_risk(
        user_id="USR-1",
        booked_hours_week=55,
        capacity_hours_week=40,
        night_activity_ratio=0.6,
        context_switches=45,
    )
    assert signal.level in {RiskLevel.HIGH, RiskLevel.CRITICAL}
