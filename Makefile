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
	cd backend && PYTHONPATH=src uvicorn srp.app:create_app --factory --reload

# Carga backend/.env (credenciales CDSE, ver docs/credenciales-cdse.md) si existe
worker:
	cd backend && if [ -f .env ]; then set -a; . ./.env; set +a; fi; PYTHONPATH=src python -m srp.worker

worker-una-vez:
	cd backend && if [ -f .env ]; then set -a; . ./.env; set +a; fi; PYTHONPATH=src python -m srp.worker --una-vez

front:
	cd frontend && npm run dev
