from pathlib import Path

from fastapi.testclient import TestClient

from .helpers import load_module

ROOT = Path(__file__).resolve().parents[2]


def test_task_pipeline_core() -> None:
    project_module = load_module("project_module", ROOT / "project-service" / "app" / "main.py")
    task_module = load_module("task_module", ROOT / "task-service" / "app" / "main.py")
    resource_module = load_module("resource_module", ROOT / "resource-service" / "app" / "main.py")
    notification_module = load_module("notification_module", ROOT / "notification-service" / "app" / "main.py")
    analytics_module = load_module("analytics_module", ROOT / "analytics-service" / "app" / "main.py")

    project_client = TestClient(project_module.app)
    task_client = TestClient(task_module.app)
    resource_client = TestClient(resource_module.app)
    notification_client = TestClient(notification_module.app)
    analytics_client = TestClient(analytics_module.app)

    project_resp = project_client.post(
        "/projects",
        json={
            "name": "Integration Project",
            "methodology": "scrum",
            "owner_id": "PM-001",
            "team_ids": ["USR-1001", "USR-1002"],
            "start_date": "2026-04-24",
            "due_date": "2026-05-24",
            "template_id": "tpl-scrum",
            "actor_role": "project_manager",
        },
    )
    assert project_resp.status_code == 200
    project_id = project_resp.json()["project_id"]

    profile_resp = resource_client.post(
        "/employees",
        json={
            "user_id": "USR-1001",
            "name": "Dev One",
            "skills": ["backend", "api"],
            "quality_score": 0.88,
            "actor_id": "PM-001",
            "actor_role": "project_manager",
        },
    )
    assert profile_resp.status_code == 200

    allocation_resp = resource_client.post(
        "/allocations",
        json={
            "user_id": "USR-1001",
            "project_id": project_id,
            "capacity_hours_week": 40,
            "booked_hours_week": 20,
            "actor_id": "PM-001",
            "actor_role": "project_manager",
        },
    )
    assert allocation_resp.status_code == 200

    task_resp = task_client.post(
        "/tasks",
        json={
            "project_id": project_id,
            "title": "Implement gateway endpoint",
            "description": "Add workflow endpoint",
            "priority": "high",
            "actor_id": "PM-001",
            "actor_role": "project_manager",
        },
    )
    assert task_resp.status_code == 200
    task = task_resp.json()

    assign_resp = resource_client.post(
        "/assign/auto",
        json={
            "task_id": task["task_id"],
            "project_id": project_id,
            "task_tags": ["backend", "api"],
            "actor_id": "PM-001",
            "actor_role": "project_manager",
        },
    )
    assert assign_resp.status_code == 200
    recommendation = assign_resp.json()["recommendation"]
    assert recommendation is not None

    update_resp = task_client.put(
        f"/tasks/{task['task_id']}",
        json={
            "assignee_id": recommendation["user_id"],
            "actor_id": "PM-001",
            "actor_role": "project_manager",
        },
    )
    assert update_resp.status_code == 200

    notify_resp = notification_client.post(
        "/notify/task-assigned",
        json={
            "task_id": task["task_id"],
            "project_id": project_id,
            "assignee_id": recommendation["user_id"],
            "title": task["title"],
            "actor_role": "project_manager",
        },
    )
    assert notify_resp.status_code == 200

    ingest_resp = analytics_client.post(
        "/analytics/ingest/task-event",
        json={
            "project_id": project_id,
            "story_points": 5,
            "status": "done",
            "actor_role": "project_manager",
        },
    )
    assert ingest_resp.status_code == 200

    forecast_resp = analytics_client.post(
        "/analytics/forecast",
        params={"actor_role": "project_manager"},
        json={
            "project_id": project_id,
            "completed_story_points_history": [3, 5, 4, 4, 6, 5, 4],
            "target_story_points": 60,
        },
    )
    assert forecast_resp.status_code == 200
    assert forecast_resp.json()["predicted_days_to_complete"] > 0


def test_risk_and_storage_flow() -> None:
    risk_module = load_module("risk_module", ROOT / "risk-service" / "app" / "main.py")
    storage_module = load_module("storage_module", ROOT / "storage-service" / "app" / "main.py")

    risk_client = TestClient(risk_module.app)
    storage_client = TestClient(storage_module.app)

    risk_resp = risk_client.post(
        "/risks",
        json={
            "project_id": "PRJ-001",
            "title": "Scope growth",
            "description": "Uncontrolled backlog expansion",
            "probability": 0.7,
            "impact": 0.8,
            "mitigation_plan": "Weekly scope validation with stakeholders and strict change approval.",
            "actor_id": "PM-001",
            "actor_role": "project_manager",
        },
    )
    assert risk_resp.status_code == 200

    score_resp = risk_client.get("/projects/PRJ-001/score", params={"actor_role": "team_lead"})
    assert score_resp.status_code == 200
    assert score_resp.json()["risk_index"] > 0

    log_resp = storage_client.post(
        "/logs",
        json={
            "operation": "task.create",
            "entity_type": "task",
            "entity_id": "TASK-00001",
            "payload": {"project_id": "PRJ-001"},
            "sensitive_payload": "vendor_contract_price=10000",
            "actor_id": "PM-001",
            "actor_role": "project_manager",
        },
    )
    assert log_resp.status_code == 200

    logs_resp = storage_client.get("/logs", params={"actor_role": "admin"})
    assert logs_resp.status_code == 200
    assert logs_resp.json()["items"]
