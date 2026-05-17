from __future__ import annotations

from datetime import UTC, date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Methodology(str, Enum):
    AGILE = "agile"
    SCRUM = "scrum"
    KANBAN = "kanban"
    WATERFALL = "waterfall"
    HYBRID = "hybrid"


class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TaskStatus(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    DONE = "done"
    BLOCKED = "blocked"


class BoardView(str, Enum):
    KANBAN = "kanban"
    LIST = "list"
    CALENDAR = "calendar"


class Role(str, Enum):
    MEMBER = "member"
    TEAM_LEAD = "team_lead"
    PROJECT_MANAGER = "project_manager"
    ADMIN = "admin"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Attachment(BaseModel):
    file_id: str
    filename: str
    content_type: str
    size_bytes: int
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ChecklistItem(BaseModel):
    item_id: str
    text: str
    done: bool = False


class Comment(BaseModel):
    comment_id: str
    author_id: str
    text: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Milestone(BaseModel):
    milestone_id: str
    title: str
    due_date: date
    done: bool = False


class ProjectTemplate(BaseModel):
    template_id: str
    name: str
    methodology: Methodology
    default_columns: list[str] = Field(default_factory=lambda: ["todo", "in_progress", "review", "done"])
    default_milestones: list[dict[str, str]] = Field(default_factory=list)


class ProjectCreateRequest(BaseModel):
    name: str
    methodology: Methodology
    owner_id: str
    team_ids: list[str] = Field(default_factory=list)
    start_date: date
    due_date: date
    template_id: str | None = None
    actor_role: Role


class Project(BaseModel):
    project_id: str
    name: str
    methodology: Methodology
    owner_id: str
    team_ids: list[str]
    start_date: date
    due_date: date
    milestones: list[Milestone] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TaskCreateRequest(BaseModel):
    project_id: str
    title: str
    description: str = ""
    assignee_id: str | None = None
    due_date: date | None = None
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.TODO
    checklist: list[ChecklistItem] = Field(default_factory=list)
    attachments: list[Attachment] = Field(default_factory=list)
    comments: list[Comment] = Field(default_factory=list)
    actor_id: str
    actor_role: Role


class Task(BaseModel):
    task_id: str
    project_id: str
    title: str
    description: str
    assignee_id: str | None
    due_date: date | None
    priority: TaskPriority
    status: TaskStatus
    checklist: list[ChecklistItem] = Field(default_factory=list)
    attachments: list[Attachment] = Field(default_factory=list)
    comments: list[Comment] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ResourceAllocation(BaseModel):
    user_id: str
    project_id: str
    capacity_hours_week: float = Field(gt=0)
    booked_hours_week: float = Field(ge=0)
    vacations: list[tuple[date, date]] = Field(default_factory=list)
    sick_leaves: list[tuple[date, date]] = Field(default_factory=list)


class RiskItem(BaseModel):
    risk_id: str
    project_id: str
    title: str
    description: str
    probability: float = Field(ge=0, le=1)
    impact: float = Field(ge=0, le=1)
    level: RiskLevel
    mitigation_plan: str
    owner_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class BurnoutSignal(BaseModel):
    user_id: str
    overload_ratio: float = Field(ge=0)
    night_activity_ratio: float = Field(ge=0, le=1)
    context_switches: int = Field(ge=0)
    risk_score: float = Field(ge=0, le=1)
    level: RiskLevel


class ForecastRequest(BaseModel):
    project_id: str
    completed_story_points_history: list[float] = Field(min_length=7)
    target_story_points: float = Field(gt=0)


class ForecastResult(BaseModel):
    project_id: str
    predicted_days_to_complete: int
    confidence: float = Field(ge=0, le=1)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class BurndownPoint(BaseModel):
    day: int
    planned_remaining: float
    actual_remaining: float


class NotificationPayload(BaseModel):
    channel: str = Field(pattern="^(email|push|slack|telegram|webhook)$")
    recipient: str
    subject: str
    body: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AuditEvent(BaseModel):
    event_id: str
    actor_id: str
    actor_role: Role | str
    action: str
    object_type: str
    object_id: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TaskWorkflowRequest(BaseModel):
    task: TaskCreateRequest
    auto_assign: bool = True
    notify: bool = True
    actor_id: str


class TaskWorkflowResult(BaseModel):
    task: dict[str, Any]
    assignee: dict[str, Any] | None
    notification: dict[str, Any] | None
    analytics: dict[str, Any] | None
    completed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
