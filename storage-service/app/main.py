from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from shared.taskflow_common import Role, Settings, encrypt_text, has_permission

settings = Settings(service_name="storage-service", service_port=8207)
app = FastAPI(title="TaskFlow Storage Service", version="1.0.0")

files: dict[str, dict[str, Any]] = {}
operation_log: list[dict[str, Any]] = []


class FileRegisterRequest(BaseModel):
    filename: str
    content_type: str
    size_bytes: int = Field(gt=0)
    project_id: str
    tags: list[str] = Field(default_factory=list)
    actor_id: str
    actor_role: Role


class OperationLogRequest(BaseModel):
    operation: str
    entity_type: str
    entity_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    sensitive_payload: str | None = None
    actor_id: str
    actor_role: Role


FileRegisterRequest.model_rebuild()
OperationLogRequest.model_rebuild()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.post("/files/register")
async def register_file(request: FileRegisterRequest) -> dict[str, Any]:
    if request.actor_role not in {Role.MEMBER, Role.TEAM_LEAD, Role.PROJECT_MANAGER, Role.ADMIN}:
        raise HTTPException(status_code=403, detail="Forbidden")

    file_id = str(uuid4())
    item = {
        "file_id": file_id,
        "filename": request.filename,
        "content_type": request.content_type,
        "size_bytes": request.size_bytes,
        "project_id": request.project_id,
        "tags": request.tags,
        "created_by": request.actor_id,
        "created_at": datetime.now(UTC).isoformat(),
    }
    files[file_id] = item
    return item


@app.get("/files/{file_id}")
async def get_file(file_id: str, actor_role: Role = Role.MEMBER) -> dict[str, Any]:
    if actor_role not in {Role.MEMBER, Role.TEAM_LEAD, Role.PROJECT_MANAGER, Role.ADMIN}:
        raise HTTPException(status_code=403, detail="Forbidden")
    item = files.get(file_id)
    if item is None:
        raise HTTPException(status_code=404, detail="File not found")
    return item


@app.get("/files")
async def list_files(project_id: str | None = None, actor_role: Role = Role.MEMBER) -> dict[str, Any]:
    if actor_role not in {Role.MEMBER, Role.TEAM_LEAD, Role.PROJECT_MANAGER, Role.ADMIN}:
        raise HTTPException(status_code=403, detail="Forbidden")
    items = []
    for item in files.values():
        if project_id and item["project_id"] != project_id:
            continue
        items.append(item)
    return {"items": items}


@app.post("/logs")
async def append_log(request: OperationLogRequest) -> dict[str, Any]:
    if not has_permission(request.actor_role, "storage:write") and request.actor_role not in {
        Role.PROJECT_MANAGER,
        Role.TEAM_LEAD,
    }:
        raise HTTPException(status_code=403, detail="Forbidden")

    item = {
        "log_id": str(uuid4()),
        "operation": request.operation,
        "entity_type": request.entity_type,
        "entity_id": request.entity_id,
        "payload": request.payload,
        "actor_id": request.actor_id,
        "actor_role": request.actor_role.value,
        "created_at": datetime.now(UTC).isoformat(),
    }
    if request.sensitive_payload:
        item["sensitive_payload_encrypted"] = encrypt_text(request.sensitive_payload, settings.encryption_key)
    operation_log.append(item)
    return item


@app.get("/logs")
async def list_logs(limit: int = 200, actor_role: Role = Role.ADMIN) -> dict[str, Any]:
    if not has_permission(actor_role, "audit:read"):
        raise HTTPException(status_code=403, detail="Forbidden")
    return {"items": operation_log[-limit:]}


@app.get("/logs/by-entity/{entity_type}/{entity_id}")
async def logs_by_entity(entity_type: str, entity_id: str, actor_role: Role = Role.ADMIN) -> dict[str, Any]:
    if not has_permission(actor_role, "audit:read"):
        raise HTTPException(status_code=403, detail="Forbidden")
    items = [item for item in operation_log if item["entity_type"] == entity_type and item["entity_id"] == entity_id]
    return {"items": items}
