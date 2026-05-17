# Развёртывание

## Локально (Docker)

1. Скопировать окружение:

```bash
cp .env.example .env
```

2. Поднять сервисы:

```bash
docker compose up --build -d
```

3. Проверить здоровье:

```bash
curl http://localhost:8280/health
curl http://localhost:8280/services/health
```

4. Остановить:

```bash
docker compose down
```

## Локально (без Docker)

1. Установить зависимости:

```bash
pip install -r requirements-dev.txt
```

2. Запуск сервиса:

```bash
python -m uvicorn api-gateway.app.main:app --reload --port 8200
```

## CI/CD

- `ci.yml`: lint + tests + compose validation.
- `cd.yml`: сборка Docker-образов по тегам `v*`.
