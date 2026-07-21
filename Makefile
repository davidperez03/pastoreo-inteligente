POSTGRES_PORT ?= 5432
export DATABASE_URL ?= postgresql://srp:srp@localhost:$(POSTGRES_PORT)/srp

db-up:
	docker compose up -d db
	docker compose exec db sh -c 'until pg_isready -U srp -d srp; do sleep 1; done'

db-down:
	docker compose down -v

migrate:
	cd backend && alembic upgrade head

test:
	cd backend && pytest

api:
	cd backend && uvicorn srp.app:create_app --factory --reload

worker:
	cd backend && python -m srp.worker

worker-una-vez:
	cd backend && python -m srp.worker --una-vez

front:
	cd frontend && npm run dev
