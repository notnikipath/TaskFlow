# API Overview

## Gateway

- `GET /health`
- `POST /auth/token`
- `POST /auth/verify`
- `GET /services/health`
- `POST /workflow/task`
- `POST /workflow/project-with-task`
- `GET /dashboard/{project_id}`

## Project Service

- `POST /projects`
- `GET /projects`
- `GET /projects/{project_id}`
- `POST /projects/{project_id}/milestones`
- `PUT /projects/{project_id}/team`

## Task Service

- `POST /tasks`
- `GET /tasks`
- `GET /tasks/{task_id}`
- `PUT /tasks/{task_id}`
- `POST /tasks/{task_id}/comments`
- `POST /tasks/{task_id}/checklist`
- `GET /boards/{project_id}`
- `POST /integrations/git/webhook`

## Resource Service

- `POST /employees`
- `POST /allocations`
- `POST /worklog`
- `POST /assign/auto`
- `GET /burnout/{user_id}`

## Risk Service

- `POST /risks`
- `GET /risks`
- `PUT /risks/{risk_id}`
- `GET /projects/{project_id}/matrix`
- `GET /projects/{project_id}/score`

## Analytics Service

- `POST /analytics/ingest/task-event`
- `POST /analytics/burndown/update`
- `GET /analytics/burndown/{project_id}`
- `POST /analytics/forecast`
- `GET /analytics/forecast/{project_id}`
- `POST /analytics/mape`
- `POST /analytics/gantt/plan`
- `GET /analytics/kpi`

## Notification Service

- `POST /notify/send`
- `POST /notify/task-assigned`
- `POST /notify/deadline`
- `POST /bots/subscriptions`
- `POST /bots/publish`

## Storage Service

- `POST /files/register`
- `GET /files/{file_id}`
- `POST /logs`
- `GET /logs`
