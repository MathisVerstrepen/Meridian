SHELL := /bin/bash

ROOT_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
API_DIR := $(ROOT_DIR)/api
API_VENV := $(API_DIR)/venv
API_BIN := $(API_VENV)/bin
UI_DIR := $(ROOT_DIR)/ui
DOCKER_DIR := $(ROOT_DIR)/docker

PYTHON_TARGETS := app migrations

.DEFAULT_GOAL := help

.PHONY: \
	help \
	install install-api install-ui \
	dev dev-api dev-ui infra-up infra-down migrate migration \
	lint lint-api lint-ui format format-api format-ui typecheck typecheck-api typecheck-ui \
	test test-api test-e2e test-ui-unit test-ui-e2e test-ui-e2e-smoke test-ui-e2e-full \
	build

help: ## Show available targets.
	@awk 'BEGIN { FS = ":.*##"; printf "Usage: make <target>\n\nTargets:\n" } /^[a-zA-Z0-9_.-]+:.*##/ { printf "  %-18s %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

install: install-api install-ui ## Install all local development dependencies.

install-api: ## Create the API virtualenv and install its Python and runtime dependencies.
	@test -x "$(API_BIN)/python" || python3 -m venv "$(API_VENV)"
	"$(API_BIN)/pip" install -r "$(API_DIR)/requirements.txt" -r "$(API_DIR)/requirements-dev.txt"
	cd "$(API_DIR)/app/gemini_cli_runtime" && npm install --omit=dev --ignore-scripts
	cd "$(API_DIR)/app/openai_codex_runtime" && npm install --omit=dev --ignore-scripts

install-ui: ## Install UI dependencies with pnpm.
	cd "$(UI_DIR)" && pnpm install

dev: infra-up migrate ## Start local infrastructure, migrate, then run the API and UI together.
	@api_pid=; ui_pid=; \
		cleanup() { \
			trap - INT TERM EXIT; \
			kill "$$api_pid" "$$ui_pid" 2>/dev/null || true; \
			wait "$$api_pid" "$$ui_pid" 2>/dev/null || true; \
		}; \
		trap 'cleanup; exit 130' INT TERM; \
		trap cleanup EXIT; \
		(cd "$(API_DIR)" && ./run-dev.sh) & api_pid=$$!; \
		(cd "$(UI_DIR)" && pnpm dev) & ui_pid=$$!; \
		wait -n "$$api_pid" "$$ui_pid"; status=$$?; \
		exit "$$status"

dev-api: ## Run the API development server.
	cd "$(API_DIR)" && ./run-dev.sh

dev-ui: ## Run the UI development server.
	cd "$(UI_DIR)" && pnpm dev

infra-up: ## Start local Docker development dependencies in the background.
	cd "$(DOCKER_DIR)" && ./run.sh dev -d

infra-down: ## Stop local Docker development dependencies.
	cd "$(DOCKER_DIR)" && ./run.sh dev down

migrate: ## Apply API database migrations.
	cd "$(API_DIR)" && ./run-dev.sh upgrade

ifeq ($(filter migration,$(MAKECMDGOALS)),migration)
ifeq ($(strip $(MESSAGE)),)
$(error MESSAGE is required. Usage: make migration MESSAGE="migration message")
endif
endif

migration: ## Create an API database migration revision.
	cd "$(API_DIR)" && "$(API_BIN)/alembic" revision -m "$(MESSAGE)"

lint: lint-api lint-ui ## Run all lint checks.

lint-api: ## Run the existing API lint and type checks.
	cd "$(API_DIR)" && ./run-linter.sh

lint-ui: ## Run UI lint checks.
	cd "$(UI_DIR)" && pnpm lint

format: format-api format-ui ## Format API and UI source files.

format-api: ## Format API app and migrations with Black and isort.
	cd "$(API_DIR)" && "$(API_BIN)/black" $(PYTHON_TARGETS) && "$(API_BIN)/isort" $(PYTHON_TARGETS)

format-ui: ## Format UI files with the installed Prettier.
	cd "$(UI_DIR)" && pnpm exec prettier --write .

typecheck: typecheck-api typecheck-ui ## Run all type checks.

typecheck-api: ## Run API mypy checks.
	cd "$(API_DIR)" && "$(API_BIN)/mypy" $(PYTHON_TARGETS)

typecheck-ui: ## Run UI type checks.
	cd "$(UI_DIR)" && pnpm typecheck

test: ## Run the repository test protocol.
	"$(ROOT_DIR)/scripts/run-tests.sh"

test-api: ## Run the API pytest suite.
	cd "$(API_DIR)" && "$(API_BIN)/python" -m pytest tests

test-e2e: ## Run the repository test protocol including browser tests.
	"$(ROOT_DIR)/scripts/run-tests.sh" --e2e

test-ui-unit: ## Run frontend unit/component tests; pass optional Vitest CLI arguments with ARGS.
	cd "$(UI_DIR)" && pnpm test:unit $(ARGS)

test-ui-e2e: test-ui-e2e-full ## Run the full frontend Playwright suite (compatibility target).

test-ui-e2e-smoke: ## Run the frontend Playwright smoke suite; pass optional CLI arguments with ARGS.
	cd "$(UI_DIR)" && pnpm test:e2e:smoke $(ARGS)

test-ui-e2e-full: ## Run the full frontend Playwright suite; pass optional CLI arguments with ARGS.
	cd "$(UI_DIR)" && pnpm test:e2e:full $(ARGS)

build: ## Build and start local Docker images in the background.
	cd "$(DOCKER_DIR)" && ./run.sh build -d
