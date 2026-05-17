# Demo Script

1. Запустить платформу:

```bash
docker compose up --build -d
```

2. Проверить gateway:

```bash
curl http://localhost:8280/health
```

3. Выполнить workflow создания задачи:

```bash
python scripts/demo_pipeline.py
```

4. Открыть UI:

- `http://localhost:5175`

5. Показать ключевые API:

- `/services/health`
- `/dashboard/PRJ-DEMO`
- `/analytics/kpi`

6. Продемонстрировать audit/logging:

- `GET /logs?actor_role=admin`
- `GET /task-service/audit` (через прямой сервис).
