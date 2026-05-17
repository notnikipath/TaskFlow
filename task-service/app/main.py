from __future__ import annotations

import re
import time
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from shared.taskflow_common import (
    BoardView,
    ChecklistItem,
    Comment,
    Role,
    Settings,
    Task,
    TaskCreateRequest,
    TaskPriority,
    TaskStatus,
    TTLCache,
    build_audit_event,
    estimate_task_days,
    has_permission,
)

settings = Settings(service_name="task-service", service_port=8202)
app = FastAPI(title="TaskFlow Task Service", version="1.0.0")

tasks: dict[str, Task] = {}
audit_log: list[dict[str, Any]] = []
git_events: list[dict[str, Any]] = []
board_cache = TTLCache(ttl_seconds=90)
_task_counter = 0


class TaskUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    assignee_id: str | None = None
    due_date: date | None = None
    priority: TaskPriority | None = None
    status: TaskStatus | None = None
    actor_id: str
    actor_role: Role


class CommentRequest(BaseModel):
    text: str = Field(min_length=1)
    actor_id: str
    actor_role: Role


class ChecklistRequest(BaseModel):
    text: str = Field(min_length=1)
    actor_id: str
    actor_role: Role


class EstimateRequest(BaseModel):
    priority: TaskPriority
    complexity: float = Field(ge=0.5, le=3.0)
    historical_cycle_days: list[float] = Field(default_factory=list)


class GitCommit(BaseModel):
    sha: str
    author: str
    message: str


class GitWebhookRequest(BaseModel):
    repository: str
    branch: str
    commits: list[GitCommit] = Field(default_factory=list)
    actor_role: Role = Role.ADMIN


TaskUpdateRequest.model_rebuild()
CommentRequest.model_rebuild()
ChecklistRequest.model_rebuild()
EstimateRequest.model_rebuild()
GitCommit.model_rebuild()
GitWebhookRequest.model_rebuild()


def _next_task_id() -> str:
    global _task_counter
    _task_counter += 1
    return f"TASK-{_task_counter:05d}"


def _assert_permission(role: Role, action: str) -> None:
    if not has_permission(role, action):
        raise HTTPException(status_code=403, detail=f"Role {role.value} cannot {action}")


def _can_update(task: Task, actor_id: str, actor_role: Role) -> bool:
    if has_permission(actor_role, "task:update"):
        return True
    return has_permission(actor_role, "task:update:own") and task.assignee_id == actor_id


def _invalidate_board(project_id: str) -> None:
    for view in BoardView:
        board_cache.set(f"board:{project_id}:{view.value}", None)


def _append_audit(
    actor_id: str,
    actor_role: Role,
    action: str,
    object_id: str,
    details: dict[str, Any] | None = None,
) -> None:
    audit_log.append(
        build_audit_event(
            actor_id=actor_id,
            actor_role=actor_role,
            action=action,
            object_type="task",
            object_id=object_id,
            details=details or {},
        ).model_dump(mode="json")
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.post("/tasks")
async def create_task(request: TaskCreateRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "task:create")

    estimated_days: float | None = None
    due_date = request.due_date
    if due_date is None:
        estimated_days = estimate_task_days(request.priority, complexity=1.0, historical_cycle_days=[2.0, 3.0, 5.0])
        due_date = date.today() + timedelta(days=max(1, int(round(estimated_days))))

    task = Task(
        task_id=_next_task_id(),
        project_id=request.project_id,
        title=request.title,
        description=request.description,
        assignee_id=request.assignee_id,
        due_date=due_date,
        priority=request.priority,
        status=request.status,
        checklist=request.checklist,
        attachments=request.attachments,
        comments=request.comments,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    tasks[task.task_id] = task
    _append_audit(
        actor_id=request.actor_id,
        actor_role=request.actor_role,
        action="task.create",
        object_id=task.task_id,
        details={"project_id": task.project_id, "assignee_id": task.assignee_id},
    )
    _invalidate_board(task.project_id)

    payload = task.model_dump(mode="json")
    payload["estimated_days"] = estimated_days
    return payload


@app.get("/tasks/{task_id}")
async def get_task(task_id: str, actor_role: Role = Role.MEMBER) -> dict[str, Any]:
    _assert_permission(actor_role, "task:read")
    task = tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task.model_dump(mode="json")


@app.get("/tasks")
async def list_tasks(
    actor_id: str,
    actor_role: Role,
    project_id: str | None = None,
    assignee_id: str | None = None,
    status: TaskStatus | None = None,
) -> dict[str, Any]:
    _assert_permission(actor_role, "task:read")

    items: list[dict[str, Any]] = []
    for task in tasks.values():
        if project_id and task.project_id != project_id:
            continue
        if assignee_id and task.assignee_id != assignee_id:
            continue
        if status and task.status != status:
            continue
        if actor_role == Role.MEMBER and task.assignee_id not in {actor_id, None}:
            continue
        items.append(task.model_dump(mode="json"))
    return {"items": items}


@app.put("/tasks/{task_id}")
async def update_task(task_id: str, request: TaskUpdateRequest) -> dict[str, Any]:
    task = tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if not _can_update(task, request.actor_id, request.actor_role):
        raise HTTPException(status_code=403, detail="Forbidden")

    if request.title is not None:
        task.title = request.title
    if request.description is not None:
        task.description = request.description
    if request.assignee_id is not None:
        task.assignee_id = request.assignee_id
    if request.due_date is not None:
        task.due_date = request.due_date
    if request.priority is not None:
        task.priority = request.priority
    if request.status is not None:
        task.status = request.status

    task.updated_at = datetime.now(UTC)
    _append_audit(request.actor_id, request.actor_role, "task.update", task_id)
    _invalidate_board(task.project_id)
    return task.model_dump(mode="json")


@app.post("/tasks/{task_id}/comments")
async def add_comment(task_id: str, request: CommentRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "task:read")
    task = tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    item = Comment(comment_id=f"CMT-{len(task.comments) + 1}", author_id=request.actor_id, text=request.text)
    task.comments.append(item)
    task.updated_at = datetime.now(UTC)
    _append_audit(request.actor_id, request.actor_role, "task.comment", task_id)
    return item.model_dump(mode="json")


@app.post("/tasks/{task_id}/checklist")
async def add_checklist(task_id: str, request: ChecklistRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "task:update")
    task = tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    item = ChecklistItem(item_id=f"CHK-{len(task.checklist) + 1}", text=request.text)
    task.checklist.append(item)
    task.updated_at = datetime.now(UTC)
    _append_audit(request.actor_id, request.actor_role, "task.checklist_add", task_id)
    return item.model_dump(mode="json")


@app.post("/tasks/estimate")
async def estimate_task(request: EstimateRequest) -> dict[str, Any]:
    days = estimate_task_days(request.priority, request.complexity, request.historical_cycle_days)
    return {"estimated_days": days, "mape_target": settings.forecast_mape_target}


@app.get("/boards/{project_id}")
async def board(project_id: str, view: BoardView = BoardView.KANBAN) -> dict[str, Any]:
    started = time.perf_counter()
    cache_key = f"board:{project_id}:{view.value}"
    cached = board_cache.get(cache_key)
    if cached is not None:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return {
            "project_id": project_id,
            "view": view.value,
            "elapsed_ms": elapsed_ms,
            "target_ms": settings.board_load_target_ms,
            "cached": True,
            "data": cached,
        }

    selected = [task for task in tasks.values() if task.project_id == project_id]
    if view == BoardView.KANBAN:
        data: Any = defaultdict(list)
        for task in selected:
            data[task.status.value].append(task.model_dump(mode="json"))
        normalized: dict[str, Any] = dict(data)
    elif view == BoardView.CALENDAR:
        normalized = sorted(
            [task.model_dump(mode="json") for task in selected],
            key=lambda item: item.get("due_date") or "9999-12-31",
        )
    else:
        normalized = [task.model_dump(mode="json") for task in selected]

    board_cache.set(cache_key, normalized)
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return {
        "project_id": project_id,
        "view": view.value,
        "elapsed_ms": elapsed_ms,
        "target_ms": settings.board_load_target_ms,
        "cached": False,
        "data": normalized,
    }


@app.post("/integrations/git/webhook")
async def git_webhook(request: GitWebhookRequest) -> dict[str, Any]:
    if request.actor_role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Only admin can post git webhook")

    linked: list[dict[str, Any]] = []
    for commit in request.commits:
        message_upper = commit.message.upper()
        matches = re.findall(r"TASK-\d+", message_upper)
        for raw_id in matches:
            task = tasks.get(raw_id)
            if task is None:
                continue
            if any(word in message_upper for word in ["DONE", "CLOSE", "FIX"]):
                task.status = TaskStatus.DONE
            else:
                task.status = TaskStatus.IN_PROGRESS
            task.updated_at = datetime.now(UTC)
            _invalidate_board(task.project_id)
            linked.append({"task_id": task.task_id, "sha": commit.sha, "status": task.status.value})

    git_event = {
        "repository": request.repository,
        "branch": request.branch,
        "processed_commits": len(request.commits),
        "linked_tasks": linked,
        "received_at": datetime.now(UTC).isoformat(),
    }
    git_events.append(git_event)
    return git_event


@app.get("/integrations/git/events")
async def list_git_events(limit: int = 100) -> dict[str, Any]:
    return {"items": git_events[-limit:]}


@app.get("/audit")
async def get_audit(limit: int = 100, actor_role: Role = Role.ADMIN) -> dict[str, Any]:
    _assert_permission(actor_role, "audit:read")
    return {"items": audit_log[-limit:]}
