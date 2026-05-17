from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from shared.taskflow_common import (
    ProjectCreateRequest,
    Role,
    Settings,
    TaskCreateRequest,
    TaskPriority,
    TaskWorkflowResult,
    sign_token,
    verify_token,
)


class GatewaySettings(BaseSettings):
    service_name: str = "api-gateway"
    service_port: int = 8200

    project_service_url: str = "http://project-service:8201"
    task_service_url: str = "http://task-service:8202"
    resource_service_url: str = "http://resource-service:8203"
    risk_service_url: str = "http://risk-service:8204"
    analytics_service_url: str = "http://analytics-service:8205"
    notification_service_url: str = "http://notification-service:8206"
    storage_service_url: str = "http://storage-service:8207"

    jwt_secret: str = Settings().jwt_secret
    token_exp_minutes: int = 180

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = GatewaySettings()
app = FastAPI(title="TaskFlow API Gateway", version="1.0.0")


class AuthRequest(BaseModel):
    user_id: str
    role: Role
    language: str = Field(default="ru", pattern="^(ru|en)$")


class WorkflowTaskRequest(BaseModel):
    project_id: str
    title: str
    description: str = ""
    assignee_id: str | None = None
    due_date: date | None = None
    priority: TaskPriority = TaskPriority.MEDIUM
    task_tags: list[str] = Field(default_factory=list)
    story_points: float = Field(default=3.0, gt=0)
    actor_id: str
    actor_role: Role
    auto_assign: bool = True
    notify: bool = True


class WorkflowProjectTaskRequest(BaseModel):
    project: ProjectCreateRequest
    first_task: WorkflowTaskRequest


def _service_urls() -> dict[str, str]:
    return {
        "project": settings.project_service_url,
        "task": settings.task_service_url,
        "resource": settings.resource_service_url,
        "risk": settings.risk_service_url,
        "analytics": settings.analytics_service_url,
        "notification": settings.notification_service_url,
        "storage": settings.storage_service_url,
    }


async def _post_json(client: httpx.AsyncClient, url: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = await client.post(url, json=payload)
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    return response.json()


async def _put_json(client: httpx.AsyncClient, url: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = await client.put(url, json=payload)
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    return response.json()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.post("/auth/token")
async def issue_token(request: AuthRequest) -> dict[str, str]:
    token = sign_token(
        {
            "sub": request.user_id,
            "role": request.role.value,
            "language": request.language,
        },
        settings.jwt_secret,
        exp_minutes=settings.token_exp_minutes,
    )
    return {"access_token": token, "token_type": "Bearer"}


@app.post("/auth/verify")
async def verify_auth(token: str) -> dict[str, Any]:
    payload = verify_token(token, settings.jwt_secret)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload


@app.get("/services/health")
async def services_health() -> dict[str, Any]:
    timeout = httpx.Timeout(6.0, connect=2.0)
    result: dict[str, Any] = {}
    async with httpx.AsyncClient(timeout=timeout) as client:
        for name, base_url in _service_urls().items():
            try:
                response = await client.get(f"{base_url}/health")
                result[name] = {"status_code": response.status_code, "body": response.json()}
            except Exception as exc:
                result[name] = {"status": "unreachable", "error": str(exc)}
    return result


@app.post("/workflow/task", response_model=TaskWorkflowResult)
async def workflow_task(request: WorkflowTaskRequest) -> TaskWorkflowResult:
    urls = _service_urls()
    timeout = httpx.Timeout(20.0, connect=5.0)

    task_request = TaskCreateRequest(
        project_id=request.project_id,
        title=request.title,
        description=request.description,
        assignee_id=request.assignee_id,
        due_date=request.due_date,
        priority=request.priority,
        actor_id=request.actor_id,
        actor_role=request.actor_role,
    )

    async with httpx.AsyncClient(timeout=timeout) as client:
        task = await _post_json(client, f"{urls['task']}/tasks", task_request.model_dump(mode="json"))

        assignee: dict[str, Any] | None = None
        if request.auto_assign:
            assignee = await _post_json(
                client,
                f"{urls['resource']}/assign/auto",
                {
                    "task_id": task["task_id"],
                    "project_id": request.project_id,
                    "task_tags": request.task_tags,
                    "due_date": task.get("due_date"),
                    "actor_id": request.actor_id,
                    "actor_role": request.actor_role.value,
                },
            )
            recommendation = assignee.get("recommendation") if assignee else None
            recommended_user = recommendation.get("user_id") if recommendation else None
            if recommended_user and not task.get("assignee_id"):
                task = await _put_json(
                    client,
                    f"{urls['task']}/tasks/{task['task_id']}",
                    {
                        "assignee_id": recommended_user,
                        "actor_id": request.actor_id,
                        "actor_role": request.actor_role.value,
                    },
                )

        notification: dict[str, Any] | None = None
        if request.notify and task.get("assignee_id"):
            notification = await _post_json(
                client,
                f"{urls['notification']}/notify/task-assigned",
                {
                    "task_id": task["task_id"],
                    "project_id": task["project_id"],
                    "assignee_id": task["assignee_id"],
                    "title": task["title"],
                    "actor_role": request.actor_role.value,
                },
            )

        analytics = await _post_json(
            client,
            f"{urls['analytics']}/analytics/ingest/task-event",
            {
                "project_id": request.project_id,
                "story_points": request.story_points,
                "status": task["status"],
                "actor_role": request.actor_role.value,
            },
        )

        await _post_json(
            client,
            f"{urls['storage']}/logs",
            {
                "operation": "workflow.task.create",
                "entity_type": "task",
                "entity_id": task["task_id"],
                "payload": {
                    "project_id": task["project_id"],
                    "assignee_id": task.get("assignee_id"),
                    "auto_assign": request.auto_assign,
                    "notify": request.notify,
                },
                "actor_id": request.actor_id,
                "actor_role": request.actor_role.value,
            },
        )

    return TaskWorkflowResult(
        task=task,
        assignee=assignee,
        notification=notification,
        analytics=analytics,
        completed_at=datetime.now(UTC),
    )


@app.post("/workflow/project-with-task")
async def workflow_project_with_task(request: WorkflowProjectTaskRequest) -> dict[str, Any]:
    urls = _service_urls()
    timeout = httpx.Timeout(30.0, connect=5.0)

    async with httpx.AsyncClient(timeout=timeout) as client:
        created_project = await _post_json(
            client,
            f"{urls['project']}/projects",
            request.project.model_dump(mode="json"),
        )

    task_payload = request.first_task.model_dump(mode="json")
    task_payload["project_id"] = created_project["project_id"]
    pipeline = await workflow_task(WorkflowTaskRequest(**task_payload))

    return {
        "project": created_project,
        "pipeline": pipeline.model_dump(mode="json"),
    }


@app.get("/dashboard/{project_id}")
async def project_dashboard(project_id: str, actor_role: Role = Role.TEAM_LEAD) -> dict[str, Any]:
    urls = _service_urls()
    timeout = httpx.Timeout(15.0, connect=4.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        board_resp = await client.get(f"{urls['task']}/boards/{project_id}", params={"view": "kanban"})
        forecast_resp = await client.get(
            f"{urls['analytics']}/analytics/forecast/{project_id}",
            params={"actor_role": actor_role.value},
        )
        risk_resp = await client.get(
            f"{urls['risk']}/projects/{project_id}/score",
            params={"actor_role": actor_role.value},
        )

    if board_resp.status_code >= 400:
        raise HTTPException(status_code=board_resp.status_code, detail=board_resp.text)
    if forecast_resp.status_code >= 400:
        raise HTTPException(status_code=forecast_resp.status_code, detail=forecast_resp.text)
    if risk_resp.status_code >= 400:
        raise HTTPException(status_code=risk_resp.status_code, detail=risk_resp.text)

    return {
        "project_id": project_id,
        "board": board_resp.json(),
        "forecast": forecast_resp.json(),
        "risk": risk_resp.json(),
        "generated_at": datetime.now(UTC).isoformat(),
    }
