# Entry point for humans and agents (ADR-0006). `make help` lists targets.
SHELL := /bin/bash
.DEFAULT_GOAL := help

BACKEND  := backend
FRONTEND := frontend
UV       := uv --directory $(BACKEND)
NPM      := npm --prefix $(FRONTEND)
NPX      := cd $(FRONTEND) && npx

# testcontainers must reach the active Docker daemon (Colima, Docker Desktop, CI runner).
DOCKER_HOST ?= $(shell docker context inspect --format '{{.Endpoints.docker.Host}}' 2>/dev/null)
export DOCKER_HOST
export TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE ?= /var/run/docker.sock

.PHONY: help install hooks up down reset logs lint format typecheck test test-fast test-one \
        test-frontend e2e req-coverage guardrails openapi

help: ## List targets
	@grep -hE '^[a-z0-9-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

install: ## Install backend and frontend dependencies, Playwright browsers, git hooks
	$(UV) sync --locked
	$(NPM) ci
	$(NPX) playwright install chromium firefox
	$(MAKE) hooks

hooks: ## Install pre-commit hooks (GOV layer: pre-commit)
	uvx pre-commit install --install-hooks

up: ## Build and start the full stack (UI on http://127.0.0.1:8080)
	docker compose up -d --build --wait

down: ## Stop the stack, keep data
	docker compose down

reset: ## Stop the stack and delete all data (GOV-006)
	docker compose down -v

logs: ## Follow logs from all services
	docker compose logs -f

lint: ## Lint + format check + type check, backend and frontend
	$(UV) run ruff check .
	$(UV) run ruff format --check .
	$(UV) run mypy
	$(NPM) run lint
	$(NPM) run format:check
	$(NPM) run typecheck

format: ## Auto-format backend and frontend
	$(UV) run ruff check --fix .
	$(UV) run ruff format .
	$(NPM) run format

test: ## All backend tests (unit, integration, contract) with coverage floor, + frontend unit
	$(UV) run pytest -m "not perf and not e2e" --cov --cov-report=term
	$(NPM) test

test-fast: ## Unit tests only, no Docker (< 10 s) — used by the agent Stop hook
	$(UV) run pytest -m unit -q -p no:cacheprovider
	$(NPM) test -- --silent

test-one: ## One backend test: make test-one T=tests/unit/test_x.py::test_name
	@test -n "$(T)" || { echo "usage: make test-one T=tests/path.py::test_name"; exit 2; }
	$(UV) run pytest "$(T)" -vv

test-frontend: ## Frontend unit tests only
	$(NPM) test

e2e: ## End-to-end tests against the running stack (run `make up` first)
	$(NPX) playwright test

req-coverage: ## Report requirement IDs without tests (GOV-016)
	python3 scripts/governance/req_coverage.py

guardrails: ## Run the governance checks CI runs (suppressions, thresholds, pins, permissions)
	uvx pre-commit run --all-files
	python3 scripts/governance/check_thresholds.py
	python3 scripts/governance/check_workflows.py

openapi: ## Regenerate docs/openapi.json from the API (review the diff!)
	$(UV) run python -c "import json; from telemetry.api.app import create_app; from telemetry.config import Settings; print(json.dumps(create_app(Settings('postgresql://unused@localhost/x')).openapi(), indent=2, sort_keys=True))" > docs/openapi.json
