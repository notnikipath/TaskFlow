from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from tests.integration.helpers import load_module

ROOT = Path(__file__).resolve().parents[2]
gateway = load_module("dashboard_gateway", ROOT / "api-gateway" / "app" / "main.py")
task = TestClient(load_module("dashboard_tasks", ROOT / "task-service" / "app" / "main.py").app)
analytics = TestClient(load_module("dashboard_analytics", ROOT / "analytics-service" / "app" / "main.py").app)
risk = TestClient(load_module("dashboard_risks", ROOT / "risk-service" / "app" / "main.py").app)
original_async_client = httpx.AsyncClient


def configure_upstreams(monkeypatch) -> None:
    def dispatch(request: httpx.Request) -> httpx.Response:
        clients = {"task-service": task, "analytics-service": analytics, "risk-service": risk}
        response = clients[request.url.host].get(request.url.path, params=request.url.params)
        return httpx.Response(response.status_code, headers=response.headers, content=response.content)

    def client_factory(**kwargs):
        return original_async_client(transport=httpx.MockTransport(dispatch), **kwargs)

    monkeypatch.setattr(gateway.httpx, "AsyncClient", client_factory)


def test_default_dashboard_loads_board_forecast_and_risk(monkeypatch) -> None:
    configure_upstreams(monkeypatch)
    response = TestClient(gateway.app).get("/dashboard/PRJ-DEMO")
    assert response.status_code == 200, response.text
    assert {"board", "forecast", "risk"} <= response.json().keys()


def test_team_lead_does_not_gain_analytics_permission(monkeypatch) -> None:
    configure_upstreams(monkeypatch)
    response = TestClient(gateway.app).get("/dashboard/PRJ-DEMO", params={"actor_role": "team_lead"})
    assert response.status_code == 403
