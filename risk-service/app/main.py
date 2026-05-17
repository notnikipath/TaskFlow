from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from shared.taskflow_common import RiskItem, RiskLevel, Role, Settings, build_audit_event, has_permission

settings = Settings(service_name="risk-service", service_port=8204)
app = FastAPI(title="TaskFlow Risk Service", version="1.0.0")

risks: dict[str, RiskItem] = {}
audit_log: list[dict[str, Any]] = []


class RiskCreateRequest(BaseModel):
    project_id: str
    title: str
    description: str
    probability: float = Field(ge=0, le=1)
    impact: float = Field(ge=0, le=1)
    mitigation_plan: str
    owner_id: str | None = None
    actor_id: str
    actor_role: Role


class RiskUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    probability: float | None = Field(default=None, ge=0, le=1)
    impact: float | None = Field(default=None, ge=0, le=1)
    mitigation_plan: str | None = None
    owner_id: str | None = None
    actor_id: str
    actor_role: Role


RiskCreateRequest.model_rebuild()
RiskUpdateRequest.model_rebuild()


def _assert_permission(role: Role, action: str) -> None:
    if not has_permission(role, action):
        raise HTTPException(status_code=403, detail=f"Role {role.value} cannot {action}")


def _level(probability: float, impact: float) -> RiskLevel:
    score = probability * impact
    if score >= 0.65:
        return RiskLevel.CRITICAL
    if score >= 0.4:
        return RiskLevel.HIGH
    if score >= 0.2:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def _append_audit(actor_id: str, actor_role: Role, action: str, object_id: str) -> None:
    audit_log.append(
        build_audit_event(
            actor_id=actor_id,
            actor_role=actor_role,
            action=action,
            object_type="risk",
            object_id=object_id,
            details={},
        ).model_dump(mode="json")
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.post("/risks")
async def create_risk(request: RiskCreateRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "risk:create")
    item = RiskItem(
        risk_id=str(uuid4()),
        project_id=request.project_id,
        title=request.title,
        description=request.description,
        probability=request.probability,
        impact=request.impact,
        level=_level(request.probability, request.impact),
        mitigation_plan=request.mitigation_plan,
        owner_id=request.owner_id,
        created_at=datetime.now(UTC),
    )
    risks[item.risk_id] = item
    _append_audit(request.actor_id, request.actor_role, "risk.create", item.risk_id)
    return item.model_dump(mode="json")


@app.get("/risks/{risk_id}")
async def get_risk(risk_id: str, actor_role: Role = Role.TEAM_LEAD) -> dict[str, Any]:
    _assert_permission(actor_role, "risk:read")
    item = risks.get(risk_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Risk not found")
    return item.model_dump(mode="json")


@app.get("/risks")
async def list_risks(
    project_id: str | None = None,
    level: RiskLevel | None = None,
    actor_role: Role = Role.TEAM_LEAD,
) -> dict[str, Any]:
    _assert_permission(actor_role, "risk:read")
    items: list[dict[str, Any]] = []
    for item in risks.values():
        if project_id and item.project_id != project_id:
            continue
        if level and item.level != level:
            continue
        items.append(item.model_dump(mode="json"))
    return {"items": items}


@app.put("/risks/{risk_id}")
async def update_risk(risk_id: str, request: RiskUpdateRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "risk:update")
    item = risks.get(risk_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Risk not found")

    if request.title is not None:
        item.title = request.title
    if request.description is not None:
        item.description = request.description
    if request.probability is not None:
        item.probability = request.probability
    if request.impact is not None:
        item.impact = request.impact
    if request.mitigation_plan is not None:
        item.mitigation_plan = request.mitigation_plan
    if request.owner_id is not None:
        item.owner_id = request.owner_id

    item.level = _level(item.probability, item.impact)
    _append_audit(request.actor_id, request.actor_role, "risk.update", risk_id)
    return item.model_dump(mode="json")


@app.get("/projects/{project_id}/matrix")
async def risk_matrix(project_id: str, actor_role: Role = Role.TEAM_LEAD) -> dict[str, Any]:
    _assert_permission(actor_role, "risk:read")
    selected = [item for item in risks.values() if item.project_id == project_id]
    counter = Counter(item.level.value for item in selected)
    heatmap = {
        "low": counter.get("low", 0),
        "medium": counter.get("medium", 0),
        "high": counter.get("high", 0),
        "critical": counter.get("critical", 0),
    }
    return {"project_id": project_id, "heatmap": heatmap, "items": [item.model_dump(mode="json") for item in selected]}


@app.get("/projects/{project_id}/score")
async def risk_score(project_id: str, actor_role: Role = Role.TEAM_LEAD) -> dict[str, Any]:
    _assert_permission(actor_role, "risk:read")
    selected = [item for item in risks.values() if item.project_id == project_id]
    if not selected:
        return {"project_id": project_id, "risk_index": 0.0, "mitigation_coverage": 0.0}

    risk_index = round(sum(item.probability * item.impact for item in selected) / len(selected), 3)
    mitigated = [item for item in selected if len(item.mitigation_plan.strip()) > 20]
    mitigation_coverage = round(len(mitigated) / len(selected), 3)
    return {
        "project_id": project_id,
        "risk_index": risk_index,
        "mitigation_coverage": mitigation_coverage,
        "generated_at": datetime.now(UTC).isoformat(),
    }


@app.get("/audit")
async def get_audit(limit: int = 100, actor_role: Role = Role.ADMIN) -> dict[str, Any]:
    _assert_permission(actor_role, "audit:read")
    return {"items": audit_log[-limit:]}
