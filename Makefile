.PHONY: up down lint test

up:
	docker compose up --build -d

down:
	docker compose down

lint:
	python -m ruff check .

test:
	python -m pytest -q
