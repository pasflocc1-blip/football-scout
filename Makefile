# ─────────────────────────────────────────────────────────────────
# Makefile — Shortcuts per i comandi più usati
# Uso: make <comando>
# Richiede: make installato (nativo su Mac, su Windows usa Git Bash o WSL)
# ─────────────────────────────────────────────────────────────────

.PHONY: help up down build logs shell-backend shell-db test migrate import-kaggle \
        lint-backend lint-frontend clean restart

# Mostra tutti i comandi disponibili
help:
	@echo ""
	@echo " ⚽ Football Scout — Comandi disponibili"
	@echo " ────────────────────────────────────────"
	@echo "  make up              Avvia tutti i container (dev mode)"
	@echo "  make up-prod         Avvia in modalità produzione"
	@echo "  make down            Ferma i container"
	@echo "  make down-clean      Ferma e cancella i volumi (⚠️ reset DB)"
	@echo "  make build           Ribuild le immagini Docker"
	@echo "  make restart         Riavvia tutti i container"
	@echo "  make logs            Segui i log di tutti i servizi"
	@echo "  make logs-back       Log solo del backend"
	@echo "  make logs-front      Log solo del frontend"
	@echo "  make shell-backend   Shell interattiva nel container backend"
	@echo "  make shell-db        Connessione al database PostgreSQL"
	@echo "  make test            Esegui i test del backend"
	@echo "  make migrate         Esegui le migration Alembic"
	@echo "  make import-kaggle   Importa dataset FIFA da Kaggle (CSV)"
	@echo "  make recalc          Ricalcola i score di tutti i giocatori"
	@echo "  make stats           Mostra statistiche del database"
	@echo "  make lint-backend    Lint codice Python"
	@echo "  make clean           Rimuove file temporanei"
	@echo ""

# ── Docker ─────────────────────────────────────────────────────
up:
	docker compose up

up-detach:
	docker compose up -d

up-prod:
	docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

down:
	docker compose down

down-clean:
	docker compose down -v

build:
	docker compose up --build

restart:
	docker compose restart

logs:
	docker compose logs -f

logs-back:
	docker compose logs -f backend

logs-front:
	docker compose logs -f frontend

# ── Shells ──────────────────────────────────────────────────────
shell-backend:
	docker compose exec backend bash

shell-db:
	docker compose exec db psql -U football football_scout

# ── Test ────────────────────────────────────────────────────────
test:
	docker compose exec backend pytest tests/ -v --tb=short

# ── Alembic migrations ──────────────────────────────────────────
migrate:
	docker compose exec backend alembic upgrade head

migrate-rollback:
	docker compose exec backend alembic downgrade -1

migrate-status:
	docker compose exec backend alembic current

# ── Data ────────────────────────────────────────────────────────
# Uso: make import-kaggle FILE=data/players_22.csv
import-kaggle:
	docker compose exec backend python -m app.services.ingest \
		--source kaggle \
		--file /app/$(or $(FILE), data/players_22.csv) \
		--limit 5000

recalc:
	curl -s -X POST http://localhost:8000/admin/recalculate-scores | python3 -m json.tool

stats:
	curl -s http://localhost:8000/admin/stats | python3 -m json.tool

# ── Lint ────────────────────────────────────────────────────────
lint-backend:
	docker compose exec backend python -m ruff check app/

lint-frontend:
	docker compose exec frontend npm run lint

# ── Pulizia ─────────────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -name ".DS_Store" -delete 2>/dev/null || true
	@echo "Pulizia completata."
