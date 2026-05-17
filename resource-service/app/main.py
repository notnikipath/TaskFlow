from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from shared.taskflow_common import (
    ResourceAllocation,
    Role,
    Settings,
    build_audit_event,
    burnout_risk,
    has_permission,
    recommend_assignee,
)

settings = Settings(service_name="resource-service", service_port=8203)
app = FastAPI(title="TaskFlow Resource Service", version="1.0.0")

allocations: dict[tuple[str, str], ResourceAllocation] = {}
employee_profiles: dict[str, dict[str, Any]] = {}
activity_feed: dict[str, dict[str, Any]] = defaultdict(lambda: {"night_activity_ratio": 0.1, "context_switches": 8})
audit_log: list[dict[str, Any]] = []


class EmployeeProfileRequest(BaseModel):
    user_id: str
    name: str
    skills: list[str] = Field(default_factory=list)
    quality_score: float = Field(default=0.75, ge=0, le=1)
    actor_id: str
    actor_role: Role


class AllocationRequest(BaseModel):
    user_id: str
    project_id: str
    capacity_hours_week: float = Field(gt=0)
    booked_hours_week: float = Field(ge=0)
    actor_id: str
    actor_role: Role


class WorklogRequest(BaseModel):
    user_id: str
    project_id: str
    additional_hours: float = Field(gt=0)
    actor_id: str
    actor_role: Role


class AbsenceRequest(BaseModel):
    user_id: str
    project_id: str
    start_date: date
    end_date: date
    actor_id: str
    actor_role: Role


class ActivityRequest(BaseModel):
    user_id: str
    night_activity_ratio: float = Field(ge=0, le=1)
    context_switches: int = Field(ge=0)
    actor_id: str
    actor_role: Role


class AutoAssignRequest(BaseModel):
    task_id: str
    project_id: str
    task_tags: list[str] = Field(default_factory=list)
    due_date: date | None = None
    actor_id: str
    actor_role: Role


EmployeeProfileRequest.model_rebuild()
AllocationRequest.model_rebuild()
WorklogRequest.model_rebuild()
AbsenceRequest.model_rebuild()
ActivityRequest.model_rebuild()
AutoAssignRequest.model_rebuild()


def _assert_permission(role: Role, action: str) -> None:
    if not has_permission(role, action):
        raise HTTPException(status_code=403, detail=f"Role {role.value} cannot {action}")


def _append_audit(
    actor_id: str,
    actor_role: Role,
    action: str,
    object_type: str,
    object_id: str,
    details: dict[str, Any] | None = None,
) -> None:
    audit_log.append(
        build_audit_event(
            actor_id=actor_id,
            actor_role=actor_role,
            action=action,
            object_type=object_type,
            object_id=object_id,
            details=details or {},
        ).model_dump(mode="json")
    )


def _candidate_pool(project_id: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for (user_id, candidate_project_id), allocation in allocations.items():
        if candidate_project_id != project_id:
            continue
        profile = employee_profiles.get(user_id, {})
        free_hours = max(0.0, allocation.capacity_hours_week - allocation.booked_hours_week)
        candidates.append(
            {
                "user_id": user_id,
                "skills": profile.get("skills", []),
                "quality_score": profile.get("quality_score", 0.7),
                "free_hours_week": free_hours,
            }
        )
    return candidates


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.post("/employees")
async def create_employee(request: EmployeeProfileRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "resource:update")
    employee_profiles[request.user_id] = {
        "user_id": request.user_id,
        "name": request.name,
        "skills": request.skills,
        "quality_score": request.quality_score,
        "created_at": datetime.now(UTC).isoformat(),
    }
    _append_audit(request.actor_id, request.actor_role, "resource.employee_create", "employee", request.user_id)
    return employee_profiles[request.user_id]


@app.get("/employees")
async def list_employees(actor_role: Role = Role.TEAM_LEAD) -> dict[str, Any]:
    _assert_permission(actor_role, "resource:read")
    return {"items": list(employee_profiles.values())}


@app.post("/allocations")
async def upsert_allocation(request: AllocationRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "resource:update")
    key = (request.user_id, request.project_id)
    item = ResourceAllocation(
        user_id=request.user_id,
        project_id=request.project_id,
        capacity_hours_week=request.capacity_hours_week,
        booked_hours_week=request.booked_hours_week,
    )
    allocations[key] = item
    _append_audit(
        request.actor_id,
        request.actor_role,
        "resource.allocation_upsert",
        "allocation",
        f"{request.user_id}:{request.project_id}",
    )
    return item.model_dump(mode="json")


@app.post("/worklog")
async def add_worklog(request: WorklogRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "resource:update")
    key = (request.user_id, request.project_id)
    allocation = allocations.get(key)
    if allocation is None:
        raise HTTPException(status_code=404, detail="Allocation not found")
    allocation.booked_hours_week += request.additional_hours
    _append_audit(
        request.actor_id,
        request.actor_role,
        "resource.worklog_add",
        "allocation",
        f"{request.user_id}:{request.project_id}",
    )
    return allocation.model_dump(mode="json")


@app.post("/absences/vacation")
async def add_vacation(request: AbsenceRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "resource:update")
    key = (request.user_id, request.project_id)
    allocation = allocations.get(key)
    if allocation is None:
        raise HTTPException(status_code=404, detail="Allocation not found")
    allocation.vacations.append((request.start_date, request.end_date))
    _append_audit(
        request.actor_id,
        request.actor_role,
        "resource.vacation_add",
        "allocation",
        f"{request.user_id}:{request.project_id}",
    )
    return allocation.model_dump(mode="json")


@app.post("/absences/sick")
async def add_sick_leave(request: AbsenceRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "resource:update")
    key = (request.user_id, request.project_id)
    allocation = allocations.get(key)
    if allocation is None:
        raise HTTPException(status_code=404, detail="Allocation not found")
    allocation.sick_leaves.append((request.start_date, request.end_date))
    _append_audit(
        request.actor_id,
        request.actor_role,
        "resource.sick_leave_add",
        "allocation",
        f"{request.user_id}:{request.project_id}",
    )
    return allocation.model_dump(mode="json")


@app.get("/allocations")
async def list_allocations(
    actor_id: str,
    actor_role: Role,
    project_id: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    if actor_role == Role.MEMBER:
        _assert_permission(actor_role, "resource:read:own")
    else:
        _assert_permission(actor_role, "resource:read")

    items: list[dict[str, Any]] = []
    for allocation in allocations.values():
        if project_id and allocation.project_id != project_id:
            continue
        if user_id and allocation.user_id != user_id:
            continue
        if actor_role == Role.MEMBER and allocation.user_id != actor_id:
            continue
        items.append(allocation.model_dump(mode="json"))
    return {"items": items}


@app.post("/activity")
async def update_activity(request: ActivityRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "resource:update")
    activity_feed[request.user_id] = {
        "night_activity_ratio": request.night_activity_ratio,
        "context_switches": request.context_switches,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    _append_audit(request.actor_id, request.actor_role, "resource.activity_update", "employee", request.user_id)
    return {"status": "updated"}


@app.post("/assign/auto")
async def auto_assign(request: AutoAssignRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "resource:update")
    recommendation = recommend_assignee(
        task_tags=request.task_tags,
        candidates=_candidate_pool(request.project_id),
        due_date=request.due_date,
    )
    _append_audit(
        request.actor_id,
        request.actor_role,
        "resource.auto_assign",
        "task",
        request.task_id,
        details={"project_id": request.project_id, "recommendation": recommendation},
    )
    return {
        "task_id": request.task_id,
        "project_id": request.project_id,
        "recommendation": recommendation,
    }


@app.get("/burnout/{user_id}")
async def burnout_snapshot(user_id: str, actor_role: Role = Role.TEAM_LEAD) -> dict[str, Any]:
    _assert_permission(actor_role, "resource:read")
    user_allocations = [item for item in allocations.values() if item.user_id == user_id]
    if not user_allocations:
        raise HTTPException(status_code=404, detail="User allocation not found")

    booked = sum(item.booked_hours_week for item in user_allocations)
    capacity = sum(item.capacity_hours_week for item in user_allocations)
    activity = activity_feed[user_id]
    signal = burnout_risk(
        user_id=user_id,
        booked_hours_week=booked,
        capacity_hours_week=capacity,
        night_activity_ratio=float(activity["night_activity_ratio"]),
        context_switches=int(activity["context_switches"]),
    )
    return signal.model_dump(mode="json")


@app.get("/workload/{project_id}")
async def workload(project_id: str, actor_role: Role = Role.TEAM_LEAD) -> dict[str, Any]:
    _assert_permission(actor_role, "resource:read")
    items = []
    for allocation in allocations.values():
        if allocation.project_id != project_id:
            continue
        utilization = round(allocation.booked_hours_week / max(allocation.capacity_hours_week, 1.0), 2)
        items.append(
            {
                "user_id": allocation.user_id,
                "capacity_hours_week": allocation.capacity_hours_week,
                "booked_hours_week": allocation.booked_hours_week,
                "utilization": utilization,
            }
        )
    return {"project_id": project_id, "items": items}


@app.get("/audit")
async def get_audit(limit: int = 100, actor_role: Role = Role.ADMIN) -> dict[str, Any]:
    _assert_permission(actor_role, "audit:read")
    return {"items": audit_log[-limit:]}
