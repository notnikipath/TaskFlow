# TaskFlow

Интеллектуальная микросервисная платформа для управления проектами, задачами, рисками и загрузкой команды.

## Что реализовано

- Полный цикл: `проект -> задачи -> автоназначение -> уведомления -> аналитика -> аудит`.
- Микросервисы:
  - `api-gateway`
  - `project-service`
  - `task-service`
  - `resource-service`
  - `risk-service`
  - `analytics-service`
  - `notification-service`
  - `storage-service`
- RBAC роли: `member`, `team_lead`, `project_manager`, `admin`.
- Поддержка методологий: Agile/Scrum, Kanban, Waterfall, Hybrid.

## Опциональные улучшения (6)

1. Автоматическая оценка сроков задач (A1).
2. Рекомендации по исполнителям (A2).
3. Детекция выгорания сотрудников (A3).
4. Интеграция с Git через webhook (B2).
5. Slack/Telegram bot публикации (B3).
6. Параллельный расчёт Ганта + кэширование досок (C1, C2).

## Быстрый старт

```bash
docker compose up --build -d
```

Проверка:

```bash
curl http://localhost:8280/health
curl http://localhost:8280/services/health
```

Swagger:

- Gateway: `http://localhost:8280/docs`
- Services: `http://localhost:8201/docs` ... `http://localhost:8207/docs`

Frontend:

- `http://localhost:5175`

## Пример workflow

```bash
curl -X POST http://localhost:8280/workflow/task \
  -H "Content-Type: application/json" \
  -d '{
    "project_id":"PRJ-DEMO",
    "title":"Plan sprint scope",
    "description":"Create sprint backlog",
    "priority":"high",
    "task_tags":["backend","planning"],
    "story_points":5,
    "actor_id":"PM-001",
    "actor_role":"project_manager",
    "auto_assign":true,
    "notify":true
  }'
```

## Тесты и качество

```bash
pip install -r requirements-dev.txt
python -m ruff check .
python -m pytest -q
```

Load scripts:

- `tests/load/locustfile.py`
- `tests/load/k6_gateway.js`

## Документация

- Архитектура: `docs/architecture.md`
- API: `docs/api.md`
- Развёртывание: `docs/deployment.md`
- Алгоритмы: `docs/algorithms.md`
- Опциональные улучшения: `docs/optional_improvements.md`
- Отчёт: `docs/project_report.md`
- Презентация: `docs/presentation_outline.md`
- Демо: `docs/demo_script.md`
