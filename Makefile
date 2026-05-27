# Convenience targets. Use `make help` to list.

.PHONY: help up down logs backend test lint fmt

help:
	@echo "Targets:"
	@echo "  up         Start full stack (postgres, redis, qdrant, backend)"
	@echo "  up-infra   Start only postgres, redis, qdrant"
	@echo "  down       Stop and remove containers"
	@echo "  logs       Tail backend logs"
	@echo "  backend    Run backend natively with hot reload"
	@echo "  test       Run backend pytest suite"
	@echo "  lint       Ruff lint on backend"
	@echo "  fmt        Ruff format on backend"

up:
	docker compose up -d --build

up-infra:
	docker compose up -d postgres redis qdrant

down:
	docker compose down

logs:
	docker compose logs -f backend

backend:
	cd backend && uv run uvicorn app.main:app --reload

test:
	cd backend && uv run pytest

lint:
	cd backend && uv run ruff check .

fmt:
	cd backend && uv run ruff format .
