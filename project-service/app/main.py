from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from shared.taskflow_common import (
    Methodology,
    Milestone,
    Project,
    ProjectCreateRequest,
    ProjectTemplate,
    Role,
    Settings,
    build_audit_event,
    has_permission,
)

settings = Settings(service_name="project-service", service_port=8201)
app = FastAPI(title="TaskFlow Project Service", version="1.0.0")

templates: dict[str, ProjectTemplate] = {
    "tpl-scrum": ProjectTemplate(
        template_id="tpl-scrum",
        name="Scrum Sprint",
        methodology=Methodology.SCRUM,
        default_milestones=[
            {"title": "Sprint Planning", "offset_days": "1"},
            {"title": "Review", "offset_days": "10"},
            {"title": "Retrospective", "offset_days": "11"},
        ],
    ),
    "tpl-kanban": ProjectTemplate(
        template_id="tpl-kanban",
        name="Kanban Delivery",
        methodology=Methodology.KANBAN,
        default_milestones=[
            {"title": "Initial Setup", "offset_days": "1"},
            {"title": "Flow Review", "offset_days": "14"},
        ],
    ),
}
projects: dict[str, Project] = {}
audit_log: list[dict] = []


class MilestoneCreateRequest(BaseModel):
    title: str
    due_date: date
    actor_id: str
    actor_role: Role


class TeamUpdateRequest(BaseModel):
    team_ids: list[str]
    actor_id: str
    actor_role: Role


def _assert(role: Role, action: str) -> None:
    if not has_permission(role, action):
        raise HTTPException(status_code=403, detail=f"Role {role.value} cannot {action}")


def _log(
    actor_id: str,
    actor_role: Role,
    action: str,
    object_type: str,
    object_id: str,
    details: dict | None = None,
) -> None:
    event = build_audit_event(
        actor_id=actor_id,
        actor_role=actor_role,
        action=action,
        object_type=object_type,
        object_id=object_id,
        details=details or {},
    )
    audit_log.append(event.model_dump(mode="json"))


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.get("/templates")
async def list_templates() -> dict:
    return {"items": [item.model_dump(mode="json") for item in templates.values()]}


@app.post("/projects")
async def create_project(request: ProjectCreateRequest) -> dict:
    _assert(request.actor_role, "project:create")
    project_id = str(uuid4())
    milestones: list[Milestone] = []
    if request.template_id and request.template_id in templates:
        template = templates[request.template_id]
        for entry in template.default_milestones:
            offset = int(entry.get("offset_days", "0"))
            due = request.start_date + timedelta(days=offset)
            milestones.append(Milestone(milestone_id=str(uuid4()), title=entry["title"], due_date=due))
    project = Project(
        project_id=project_id,
        name=request.name,
        methodology=request.methodology,
        owner_id=request.owner_id,
        team_ids=request.team_ids,
        start_date=request.start_date,
        due_date=request.due_date,
        milestones=milestones,
        created_at=datetime.now(UTC),
    )
    projects[project_id] = project
    _log(request.owner_id, request.actor_role, "project.create", "project", project_id)
    return project.model_dump(mode="json")


@app.get("/projects/{project_id}")
async def get_project(project_id: str, actor_role: Role = Role.MEMBER) -> dict:
    _assert(actor_role, "project:read")
    project = projects.get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project.model_dump(mode="json")


@app.get("/projects")
async def list_projects(actor_role: Role = Role.MEMBER) -> dict:
    _assert(actor_role, "project:read")
    return {"items": [item.model_dump(mode="json") for item in projects.values()]}


@app.post("/projects/{project_id}/milestones")
async def create_milestone(project_id: str, request: MilestoneCreateRequest) -> dict:
    _assert(request.actor_role, "project:update")
    project = projects.get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    milestone = Milestone(milestone_id=str(uuid4()), title=request.title, due_date=request.due_date)
    project.milestones.append(milestone)
    _log(request.actor_id, request.actor_role, "project.add_milestone", "project", project_id)
    return milestone.model_dump(mode="json")


@app.put("/projects/{project_id}/team")
async def update_team(project_id: str, request: TeamUpdateRequest) -> dict:
    _assert(request.actor_role, "project:update")
    project = projects.get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    project.team_ids = request.team_ids
    _log(
        request.actor_id,
        request.actor_role,
        "project.update_team",
        "project",
        project_id,
        {"team_size": len(request.team_ids)},
    )
    return project.model_dump(mode="json")


@app.get("/audit")
async def get_audit(limit: int = 100, actor_role: Role = Role.ADMIN) -> dict:
    _assert(actor_role, "audit:read")
    return {"items": audit_log[-limit:]}
