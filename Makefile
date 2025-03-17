# Env vars
include .env
export

# Detach var for CI
DETACH ?= 0

# Version for production deployment
VERSION := 5.0

# List of services to build
SERVICES := api-service agent-service pdf-service tts-service

# Required environment variables
REQUIRED_ENV_VARS := ELEVENLABS_API_KEY NVIDIA_API_KEY MAX_CONCURRENT_REQUESTS

# Colors for terminal output
RED := \033[0;31m
GREEN := \033[0;32m
NC := \033[0m  # No Color

# Explicitly use bash
SHELL := /bin/bash

# List of all services used
CORE_SERVICES := redis minio api-service agent-service pdf-service tts-service jaeger
PDF_MODEL_SERVICES := redis pdf-api celery-worker

# Check if environment variables are set
check_env:
	@for var in $(REQUIRED_ENV_VARS); do \
		if [ -z "$$(eval echo "\$$$$var")" ]; then \
			echo "$(RED)Error: $$var is not set$(NC)"; \
			echo "Please set required environment variables:"; \
			echo "  export $$var=<value>"; \
			exit 1; \
		else \
			echo "$(GREEN)✓ $$var is set$(NC)"; \
		fi \
	done

# UV environment setup target
uv:
	@echo "$(GREEN)Setting up UV environment...$(NC)"
	@bash setup.sh

# Create the minio data directory if it doesn't exist
create-minio-data-dir:
	@if [ ! -d "data/minio" ]; then \
		echo "$(GREEN)Creating data/minio directory...$(NC)"; \
		mkdir -p data/minio; \
	fi

# Development target that does NOT locally run and build docling. Make sure to set the MODEL_API_URL environment variable to the correct URL.
dev: check_env create-minio-data-dir
	docker compose down $(CORE_SERVICES)
	@echo "$(GREEN)Starting development environment...$(NC)"
	@if [ "$(DETACH)" = "1" ]; then \
		docker compose -f docker-compose.yaml --env-file .env up $(CORE_SERVICES) --build -d; \
	else \
		docker compose -f docker-compose.yaml --env-file .env up $(CORE_SERVICES) --build; \
	fi

# Development target to build only the pdf model service (docling) for local development
model-dev:
	docker compose down $(PDF_MODEL_SERVICES)
	@echo "$(GREEN)Starting development environment...$(NC)"
	docker compose up $(PDF_MODEL_SERVICES) --build

# Development target that will run all services including the pdf model service (docling) locally
all-services: check_env create-minio-data-dir
	docker compose down
	@echo "$(GREEN)Starting development environment all-services...$(NC)"
	@if [ "$(DETACH)" = "1" ]; then \
		docker compose -f docker-compose.yaml --env-file .env up --build -d; \
	else \
		docker compose -f docker-compose.yaml --env-file .env up --build; \
	fi

# Clean up containers and volumes
clean:
	docker compose -f docker-compose.yaml down -v

# Approve a pull request manually
approve-pr:
	@read -p "Enter the PR number to approve: " PR_NUMBER; \
	if [ -z "$$PR_NUMBER" ]; then \
		echo "$(RED)Error: PR number is required$(NC)"; \
		exit 1; \
	fi; \
	gh pr review $$PR_NUMBER --approve

lint:
	ruff check

format:
	ruff format

ruff: lint format

.PHONY: check_env dev clean ruff prod version-bump version-bump-major uv model-prod model-dev all-services create-minio-data-dir approve-pr
