.PHONY: help install install-ml run run-simulator test clean docker-up docker-down docker-logs

help: ## Affiche cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Installation
install: ## Installe les dépendances backend
	pip install -r backend/requirements.txt

install-ml: ## Installe les dépendances ML
	pip install -r backend/ml/requirements-ml.txt

install-all: install install-ml ## Installe toutes les dépendances

# Développement local
run: ## Lance l'API backend
	uvicorn backend.main_v2:app --reload --host 0.0.0.0 --port 8000

run-old: ## Lance l'ancienne version de l'API
	uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

run-simulator: ## Lance le simulateur de données
	python services/simulator/simulator.py

run-frontend: ## Lance un serveur HTTP pour le frontend
	python -m http.server 8080 --directory frontend

# Tests
test: ## Lance les tests (si disponibles)
	pytest backend/tests/ -v

lint: ## Vérifie le code avec flake8
	flake8 backend/ --max-line-length=120

format: ## Formate le code avec black
	black backend/ --line-length=120

# Docker
docker-up: ## Lance tous les services avec Docker Compose
	docker-compose up -d

docker-down: ## Arrête tous les services Docker
	docker-compose down

docker-logs: ## Affiche les logs des services Docker
	docker-compose logs -f

docker-rebuild: ## Reconstruit et relance les services
	docker-compose up -d --build

docker-clean: ## Supprime tous les containers et volumes
	docker-compose down -v

# Base de données
init-db: ## Initialise la base de données SQLite
	python -c "from backend.core import get_sqlite_registry; get_sqlite_registry()"

clean-db: ## Supprime la base de données SQLite
	rm -f database/sqlite.db

# Nettoyage
clean: ## Nettoie les fichiers temporaires
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.log" -delete

clean-all: clean clean-db docker-clean ## Nettoyage complet

# Monitoring
health: ## Vérifie la santé de l'API
	curl http://localhost:8000/health | jq

stats: ## Affiche les statistiques
	@echo "=== API Stats ==="
	@curl -s http://localhost:8000/api/ingest/stats | jq
	@echo "\n=== WebSocket Stats ==="
	@curl -s http://localhost:8000/ws/stats | jq

# Production
deploy: ## Déploie l'application (TODO)
	@echo "TODO: Implémenter le déploiement"

backup: ## Sauvegarde les données
	@mkdir -p backups
	@tar -czf backups/backup-$(shell date +%Y%m%d-%H%M%S).tar.gz database/ assets/ml_models/
	@echo "Backup créé dans backups/"
