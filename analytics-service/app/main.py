from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from statistics import mean
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from shared.taskflow_common import (
    ForecastRequest,
    Role,
    Settings,
    TaskStatus,
    burndown_series,
    forecast_completion,
    gantt_parallel_hint,
    has_permission,
    mape,
)

settings = Settings(service_name="analytics-service", service_port=8205)
app = FastAPI(title="TaskFlow Analytics Service", version="1.0.0")

project_scope: dict[str, float] = defaultdict(float)
project_actual_burn: dict[str, list[float]] = defaultdict(list)
project_velocity_history: dict[str, list[float]] = defaultdict(list)
forecast_cache: dict[str, dict[str, Any]] = {}
mape_samples: list[float] = []

role_dashboards: dict[str, dict[str, Any]] = {
    "member": {"widgets": ["my_tasks", "today_deadlines", "focus_time"]},
    "team_lead": {"widgets": ["team_load", "burndown", "risk_alerts"]},
    "project_manager": {"widgets": ["gantt", "forecast", "budget_risk", "burnout"]},
    "admin": {"widgets": ["portfolio_kpi", "throughput", "audit_stream"]},
}


class TaskEventRequest(BaseModel):
    project_id: str
    story_points: float = Field(gt=0)
    status: TaskStatus
    actor_role: Role = Role.PROJECT_MANAGER


class BurndownUpdateRequest(BaseModel):
    project_id: str
    total_scope: float = Field(gt=0)
    actual_burn: list[float] = Field(default_factory=list)
    actor_role: Role = Role.PROJECT_MANAGER


class MapeRequest(BaseModel):
    actual: list[float]
    predicted: list[float]


class GanttRequest(BaseModel):
    tasks: list[dict[str, Any]] = Field(default_factory=list)
    actor_role: Role = Role.PROJECT_MANAGER


class DashboardUpdateRequest(BaseModel):
    widgets: list[str] = Field(default_factory=list)
    actor_role: Role


TaskEventRequest.model_rebuild()
BurndownUpdateRequest.model_rebuild()
MapeRequest.model_rebuild()
GanttRequest.model_rebuild()
DashboardUpdateRequest.model_rebuild()


def _assert_read(role: Role) -> None:
    if not has_permission(role, "analytics:read"):
        raise HTTPException(status_code=403, detail="Forbidden")


def _assert_write(role: Role) -> None:
    if role not in {Role.PROJECT_MANAGER, Role.ADMIN}:
        raise HTTPException(status_code=403, detail="Forbidden")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.post("/analytics/ingest/task-event")
async def ingest_task_event(request: TaskEventRequest) -> dict[str, Any]:
    _assert_write(request.actor_role)
    project_scope[request.project_id] += request.story_points
    if request.status == TaskStatus.DONE:
        project_actual_burn[request.project_id].append(request.story_points)
        project_velocity_history[request.project_id].append(request.story_points)
    return {"status": "ingested", "project_id": request.project_id}


@app.post("/analytics/burndown/update")
async def update_burndown(request: BurndownUpdateRequest) -> dict[str, Any]:
    _assert_write(request.actor_role)
    project_scope[request.project_id] = request.total_scope
    project_actual_burn[request.project_id] = request.actual_burn
    series = burndown_series(request.total_scope, request.actual_burn)
    return {"project_id": request.project_id, "items": [item.model_dump(mode="json") for item in series]}


@app.get("/analytics/burndown/{project_id}")
async def get_burndown(project_id: str, actor_role: Role = Role.TEAM_LEAD) -> dict[str, Any]:
    _assert_read(actor_role)
    scope = project_scope.get(project_id, 0.0)
    burn = project_actual_burn.get(project_id, [])
    return {
        "project_id": project_id,
        "items": [item.model_dump(mode="json") for item in burndown_series(scope, burn)],
        "target_board_load_ms": settings.board_load_target_ms,
    }


@app.post("/analytics/forecast")
async def run_forecast(request: ForecastRequest, actor_role: Role = Role.PROJECT_MANAGER) -> dict[str, Any]:
    _assert_read(actor_role)
    result = forecast_completion(
        project_id=request.project_id,
        completed_points_history=request.completed_story_points_history,
        target_points=request.target_story_points,
    )
    item = result.model_dump(mode="json")
    item["mape_target_pct"] = settings.forecast_mape_target
    forecast_cache[request.project_id] = item
    return item


@app.get("/analytics/forecast/{project_id}")
async def get_forecast(project_id: str, actor_role: Role = Role.TEAM_LEAD) -> dict[str, Any]:
    _assert_read(actor_role)
    item = forecast_cache.get(project_id)
    if item is None:
        history = project_velocity_history.get(project_id, [])
        target = max(sum(history), 1.0) * 1.3
        item = forecast_completion(project_id, history or [3.0] * 7, target).model_dump(mode="json")
        item["mape_target_pct"] = settings.forecast_mape_target
    return item


@app.post("/analytics/mape")
async def mape_stats(request: MapeRequest, actor_role: Role = Role.TEAM_LEAD) -> dict[str, Any]:
    _assert_read(actor_role)
    score = mape(request.actual, request.predicted)
    mape_samples.append(score)
    average = round(mean(mape_samples), 2) if mape_samples else score
    return {
        "mape_pct": score,
        "avg_mape_pct": average,
        "target_pct": settings.forecast_mape_target,
        "target_met": score <= settings.forecast_mape_target,
    }


@app.post("/analytics/gantt/plan")
async def gantt_plan(request: GanttRequest) -> dict[str, Any]:
    _assert_read(request.actor_role)
    plan = gantt_parallel_hint(request.tasks)
    return {
        "parallel_plan": plan,
        "throughput_target_users": settings.concurrent_users_target,
    }


@app.get("/analytics/kpi")
async def kpi(actor_role: Role = Role.PROJECT_MANAGER) -> dict[str, Any]:
    _assert_read(actor_role)
    avg_mape = round(mean(mape_samples), 2) if mape_samples else 0.0
    return {
        "board_load_target_ms": settings.board_load_target_ms,
        "forecast_mape_target_pct": settings.forecast_mape_target,
        "forecast_mape_avg_pct": avg_mape,
        "concurrent_users_target": settings.concurrent_users_target,
        "generated_at": datetime.now(UTC).isoformat(),
    }


@app.get("/dashboards/{role}")
async def get_dashboard(role: str) -> dict[str, Any]:
    dashboard = role_dashboards.get(role, role_dashboards[Role.MEMBER.value])
    return {"role": role, "dashboard": dashboard, "supported_languages": ["ru", "en"]}


@app.put("/dashboards/{role}")
async def update_dashboard(role: str, request: DashboardUpdateRequest) -> dict[str, Any]:
    if request.actor_role not in {Role.PROJECT_MANAGER, Role.ADMIN}:
        raise HTTPException(status_code=403, detail="Forbidden")
    role_dashboards[role] = {"widgets": request.widgets}
    return {"role": role, "dashboard": role_dashboards[role]}
