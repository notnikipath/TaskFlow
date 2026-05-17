from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from shared.taskflow_common import Role, Settings, has_permission

settings = Settings(service_name="notification-service", service_port=8206)
app = FastAPI(title="TaskFlow Notification Service", version="1.0.0")

messages: list[dict[str, Any]] = []
subscriptions: dict[str, dict[str, str]] = {}


class NotificationRequest(BaseModel):
    channel: str = Field(pattern="^(push|email|slack|telegram|webhook)$")
    recipient: str
    subject: str
    body: str
    actor_role: Role


class AssigneeNotificationRequest(BaseModel):
    task_id: str
    project_id: str
    assignee_id: str
    title: str
    actor_role: Role


class DeadlineRequest(BaseModel):
    task_id: str
    assignee_id: str
    due_date: str
    overdue: bool = False
    actor_role: Role


class BotSubscriptionRequest(BaseModel):
    platform: str = Field(pattern="^(slack|telegram)$")
    channel_id: str
    webhook_url: str
    actor_role: Role


class BotPublishRequest(BaseModel):
    platform: str = Field(pattern="^(slack|telegram)$")
    text: str
    actor_role: Role


NotificationRequest.model_rebuild()
AssigneeNotificationRequest.model_rebuild()
DeadlineRequest.model_rebuild()
BotSubscriptionRequest.model_rebuild()
BotPublishRequest.model_rebuild()


def _assert_send_permission(role: Role) -> None:
    if not has_permission(role, "notification:send") and role != Role.TEAM_LEAD:
        raise HTTPException(status_code=403, detail="Forbidden")


def _queue(item: dict[str, Any]) -> dict[str, Any]:
    item["id"] = str(uuid4())
    item["created_at"] = datetime.now(UTC).isoformat()
    messages.append(item)
    return item


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.post("/notify/send")
async def send(request: NotificationRequest) -> dict[str, Any]:
    _assert_send_permission(request.actor_role)
    item = _queue(request.model_dump(mode="json"))
    return {"status": "queued", "id": item["id"]}


@app.post("/notify/task-assigned")
async def notify_assignee(request: AssigneeNotificationRequest) -> dict[str, Any]:
    _assert_send_permission(request.actor_role)
    body = f"You have a new task {request.task_id} in project {request.project_id}: {request.title}"
    item = _queue(
        {
            "channel": "push",
            "recipient": request.assignee_id,
            "subject": "Task Assigned",
            "body": body,
            "actor_role": request.actor_role.value,
        }
    )
    return {"status": "queued", "id": item["id"], "recipient": request.assignee_id}


@app.post("/notify/deadline")
async def notify_deadline(request: DeadlineRequest) -> dict[str, Any]:
    _assert_send_permission(request.actor_role)
    subject = "Task Overdue" if request.overdue else "Task Deadline Reminder"
    body = (
        f"Task {request.task_id} is overdue since {request.due_date}."
        if request.overdue
        else f"Task {request.task_id} deadline is {request.due_date}."
    )
    item = _queue(
        {
            "channel": "email",
            "recipient": request.assignee_id,
            "subject": subject,
            "body": body,
            "actor_role": request.actor_role.value,
        }
    )
    return {"status": "queued", "id": item["id"]}


@app.post("/bots/subscriptions")
async def add_subscription(request: BotSubscriptionRequest) -> dict[str, Any]:
    if request.actor_role not in {Role.ADMIN, Role.PROJECT_MANAGER}:
        raise HTTPException(status_code=403, detail="Forbidden")
    subscriptions[request.platform] = {"channel_id": request.channel_id, "webhook_url": request.webhook_url}
    return {"status": "subscribed", "platform": request.platform}


@app.post("/bots/publish")
async def publish_bot(request: BotPublishRequest) -> dict[str, Any]:
    _assert_send_permission(request.actor_role)
    target = subscriptions.get(request.platform)
    if target is None:
        raise HTTPException(status_code=404, detail="Bot subscription not configured")
    item = _queue(
        {
            "channel": request.platform,
            "recipient": target["channel_id"],
            "subject": "Bot Broadcast",
            "body": request.text,
            "actor_role": request.actor_role.value,
        }
    )
    return {"status": "queued", "id": item["id"], "platform": request.platform}


@app.get("/notify/history")
async def history(limit: int = 200) -> dict[str, Any]:
    return {"items": messages[-limit:]}


@app.get("/bots/subscriptions")
async def list_subscriptions() -> dict[str, Any]:
    return {"items": subscriptions}
