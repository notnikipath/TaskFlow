# Архитектура TaskFlow

## Общая схема

`api-gateway` оркестрирует операции и связывает бизнес-сервисы.

- `project-service`: проекты, вехи, команды, шаблоны.
- `task-service`: задачи, доски, комментарии, чек-листы, Git webhook.
- `resource-service`: загрузка, отпуска/больничные, автоназначение, burnout score.
- `risk-service`: реестр рисков, матрица вероятности/влияния, риск-индекс.
- `analytics-service`: burndown, прогноз завершения, MAPE, KPI, дашборды.
- `notification-service`: уведомления, дедлайны, Slack/Telegram bots.
- `storage-service`: метаданные файлов, журнал операций, зашифрованные поля.

## Инфраструктура

- Backend: FastAPI (Python).
- Data layer: PostgreSQL, Redis, RabbitMQ, MinIO (в docker-compose).
- Frontend: React + Redux + Vite.

## Пайплайн задачи

1. Создание задачи в `task-service`.
2. Автоназначение в `resource-service`.
3. Обновление исполнителя в `task-service`.
4. Уведомление исполнителя через `notification-service`.
5. Ингест метрик в `analytics-service`.
6. Журналирование операции в `storage-service`.

## Безопасность

- RBAC на уровне endpoint'ов.
- Подпись/проверка токена (HMAC).
- Шифрование чувствительных строк в логах хранения.
- Аудит всех критичных действий.
