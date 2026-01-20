# Annotex Makefile
# Common development commands for the project
#
# Usage: make <target>
# Run 'make help' to see all available commands

.PHONY: help install install-dev setup lint format test test-cov security clean docker-build docker-up docker-down migrate run worker

# Default target
.DEFAULT_GOAL := help

# Colors for terminal output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

#-----------------------------------------------------------------------
# Help
#-----------------------------------------------------------------------
help: ## Show this help message
	@echo "$(BLUE)Annotex Development Commands$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(YELLOW)Quick Start:$(NC)"
	@echo "  make setup    - First time setup (install deps + pre-commit hooks)"
	@echo "  make dev      - Start development environment"
	@echo "  make test     - Run tests"

#-----------------------------------------------------------------------
# Setup & Installation
#-----------------------------------------------------------------------
install: ## Install production dependencies
	pip install --upgrade pip
	pip install -r requirements.txt

install-dev: install ## Install all dependencies including dev tools
	pip install pre-commit

setup: install-dev ## First-time setup: install deps + configure pre-commit hooks
	@echo "$(BLUE)Setting up pre-commit hooks...$(NC)"
	pre-commit install
	pre-commit install --hook-type pre-push
	@echo "$(GREEN)Setup complete! Pre-commit hooks are now active.$(NC)"
	@echo "$(YELLOW)Tip: Run 'make lint' to check code before committing.$(NC)"

#-----------------------------------------------------------------------
# Code Quality
#-----------------------------------------------------------------------
lint: ## Run linter (ruff)
	@echo "$(BLUE)Running ruff linter...$(NC)"
	ruff check .

lint-fix: ## Run linter and auto-fix issues
	@echo "$(BLUE)Running ruff with auto-fix...$(NC)"
	ruff check . --fix

format: ## Format code with ruff
	@echo "$(BLUE)Formatting code...$(NC)"
	ruff format .

format-check: ## Check code formatting without changes
	ruff format --check .

security: ## Run security scan (bandit)
	@echo "$(BLUE)Running security scan...$(NC)"
	bandit -r app/ -c pyproject.toml

pre-commit: ## Run all pre-commit hooks on all files
	@echo "$(BLUE)Running pre-commit hooks...$(NC)"
	pre-commit run --all-files

check: lint format-check security ## Run all checks (lint + format + security)
	@echo "$(GREEN)All checks passed!$(NC)"

#-----------------------------------------------------------------------
# Testing
#-----------------------------------------------------------------------
test: ## Run tests
	@echo "$(BLUE)Running tests...$(NC)"
	pytest tests/ -v

test-cov: ## Run tests with coverage report
	@echo "$(BLUE)Running tests with coverage...$(NC)"
	pytest tests/ -v --cov=app --cov-report=term-missing --cov-report=html
	@echo "$(GREEN)Coverage report generated in htmlcov/$(NC)"

test-fast: ## Run tests in parallel (faster)
	pytest tests/ -v -x -q

#-----------------------------------------------------------------------
# Database
#-----------------------------------------------------------------------
migrate: ## Run database migrations
	@echo "$(BLUE)Running migrations...$(NC)"
	alembic upgrade head

migrate-new: ## Create a new migration (usage: make migrate-new msg="description")
	@echo "$(BLUE)Creating new migration...$(NC)"
	alembic revision --autogenerate -m "$(msg)"

migrate-down: ## Rollback one migration
	alembic downgrade -1

#-----------------------------------------------------------------------
# Development
#-----------------------------------------------------------------------
run: ## Run the API server (development mode)
	@echo "$(BLUE)Starting API server...$(NC)"
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

worker: ## Run Celery worker
	@echo "$(BLUE)Starting Celery worker...$(NC)"
	celery -A app.workers.celery_app worker --loglevel=info

dev: docker-up ## Start full development environment
	@echo "$(GREEN)Development environment is ready!$(NC)"
	@echo "  API: http://localhost:8000"
	@echo "  Docs: http://localhost:8000/docs"

#-----------------------------------------------------------------------
# Docker
#-----------------------------------------------------------------------
docker-build: ## Build Docker images
	@echo "$(BLUE)Building Docker images...$(NC)"
	docker-compose build

docker-up: ## Start Docker containers
	@echo "$(BLUE)Starting Docker containers...$(NC)"
	docker-compose up -d
	@echo "$(GREEN)Containers started!$(NC)"

docker-down: ## Stop Docker containers
	@echo "$(BLUE)Stopping Docker containers...$(NC)"
	docker-compose down

docker-logs: ## Show Docker logs
	docker-compose logs -f

docker-clean: ## Remove all Docker containers and volumes
	@echo "$(RED)Removing all containers and volumes...$(NC)"
	docker-compose down -v --remove-orphans

#-----------------------------------------------------------------------
# CI/CD Simulation
#-----------------------------------------------------------------------
ci: check test ## Simulate CI pipeline locally (lint + security + test)
	@echo "$(GREEN)CI checks passed!$(NC)"

#-----------------------------------------------------------------------
# Cleanup
#-----------------------------------------------------------------------
clean: ## Clean up generated files
	@echo "$(BLUE)Cleaning up...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	rm -rf .eggs *.egg-info dist build 2>/dev/null || true
	@echo "$(GREEN)Cleanup complete!$(NC)"
