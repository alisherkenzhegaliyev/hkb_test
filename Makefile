.PHONY: up down build logs restart clean ps shell-api shell-db

up:
	docker-compose up -d

build:
	docker-compose up -d --build

down:
	docker-compose down

restart:
	docker-compose restart

logs:
	docker-compose logs -f

logs-api:
	docker-compose logs -f api

logs-db:
	docker-compose logs -f postgres

ps:
	docker-compose ps

shell-api:
	docker-compose exec api bash

shell-db:
	docker-compose exec postgres psql -U recruiting -d recruiting

clean:
	docker-compose down -v --remove-orphans

# ── Local dev (no Docker for API/Streamlit) ───────────────────────────────────
db:
	docker-compose up -d postgres

dev-api:
	.venv/bin/uvicorn src.api.main:app --reload --port 8000

dev-ui:
	.venv/bin/streamlit run frontend/app.py --server.port 8501
