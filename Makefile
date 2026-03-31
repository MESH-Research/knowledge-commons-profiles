# Knowledge Commons Profiles — Local Development Makefile
#
# Quick start:
#   make build   — build base image + local Django container
#   make build NO_CACHE=1 — same, but without Docker layer cache
#   make up      — start the local development server (https://localhost)
#   make down    — stop all containers
#   make test    — run the test suite inside the container
#   make logs    — tail container logs
#   make shell   — open a bash shell in the running container

COMPOSE_FILE   := docker-compose.local.yml
COMPOSE        := docker compose -f $(COMPOSE_FILE)
BASE_DOCKERFILE := compose/base/Dockerfile

# The local Dockerfile expects ${ECR_REGISTRY}/kcprofiles-base-dev:latest.
# We build the base image with this tag so it resolves without ECR access.
ECR_REGISTRY   := registry
BASE_IMAGE     := $(ECR_REGISTRY)/kcprofiles-base-dev:latest

# Pass NO_CACHE=1 to force a clean rebuild (e.g. make build NO_CACHE=1)
DOCKER_BUILD_FLAGS := $(if $(NO_CACHE),--no-cache,)

.PHONY: help build build-base build-app up down restart logs shell test \
        manage migrate lint clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

# ── Build ───────────────────────────────────────────────────────────────

build: build-base build-app ## Build everything (base image + local app)

build-base: ## Build the base dev image locally (no ECR needed)
	docker build \
		-f $(BASE_DOCKERFILE) \
		--build-arg BUILD_ENVIRONMENT=local \
		$(DOCKER_BUILD_FLAGS) \
		-t $(BASE_IMAGE) \
		.

build-app: ## Build the local Django image (requires base image)
	$(COMPOSE) build $(DOCKER_BUILD_FLAGS)

# ── Run ─────────────────────────────────────────────────────────────────

up: ## Start the local dev server (https://localhost)
	$(COMPOSE) up -d

down: ## Stop all containers
	$(COMPOSE) down

restart: down up ## Restart all containers

logs: ## Tail container logs
	$(COMPOSE) logs -f

# ── Development ─────────────────────────────────────────────────────────

shell: ## Open a bash shell in the running Django container
	$(COMPOSE) exec django bash

manage: ## Run a manage.py command (usage: make manage CMD="migrate")
	$(COMPOSE) exec django uv run python manage.py $(CMD)

migrate: ## Run database migrations
	$(COMPOSE) exec django uv run python manage.py migrate

test: ## Run the test suite
	$(COMPOSE) exec django env \
		DJANGO_SETTINGS_MODULE=config.settings.test \
		DJANGO_READ_DOT_ENV_FILE=True \
		uv run python manage.py test

lint: ## Run pre-commit hooks on all files
	uv run pre-commit run --all-files

clean: ## Remove containers, volumes, and local images
	$(COMPOSE) down -v --rmi local
