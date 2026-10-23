# Developer entrypoints. `make check` is what CI runs; keep it green before pushing.
.DEFAULT_GOAL := help
UV ?= uv
ENV ?= dev
TF_DIR ?= infra/terraform/gcp

help: ## Show targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

setup: ## Install Python deps (dev group) into .venv
	$(UV) sync --group dev

lint: ## Ruff lint + format check
	$(UV) run ruff check src tests scripts
	$(UV) run ruff format --check src tests scripts

fmt: ## Auto-format and fix lint
	$(UV) run ruff format src tests scripts
	$(UV) run ruff check --fix src tests scripts

test: ## Run the test suite
	$(UV) run pytest -q

policy: ## Repo guardrails: portability, no client data, tracker in sync
	$(UV) run python scripts/check_portability.py
	$(UV) run python scripts/check_no_client_data.py
	$(UV) run python scripts/render_tracker.py --check

secrets-scan: ## gitleaks over the working tree (requires gitleaks on PATH or docker)
	@command -v gitleaks >/dev/null && gitleaks dir . --config .gitleaks.toml --no-banner --redact \
	 || docker run --rm -v "$(PWD):/repo" ghcr.io/gitleaks/gitleaks:latest dir /repo --config /repo/.gitleaks.toml --no-banner --redact

check: lint test policy ## Everything CI runs (minus the secret scan, which needs gitleaks)

tracker: ## Re-render docs/planning/TRACKER.md from docs/planning/tracker/*.yaml
	$(UV) run python scripts/render_tracker.py

catalog: ## Regenerate the CCM/CAIQ JSON from reference/ spreadsheets
	$(UV) run python scripts/build_control_catalog.py

demo: ## Assess the synthetic sample offline and print the report
	$(UV) run readiness assess tests/fixtures/synthetic_acme --profile default --snippets

serve: ## Run the API locally (auth disabled)
	READINESS_AUTH_DISABLED=true $(UV) run readiness serve --port 8080

docker-build: ## Build the container
	docker build -t readiness:local .

docker-run: ## Run the container locally on :8080
	docker run --rm -p 8080:8080 --env-file .env -e READINESS_AUTH_DISABLED=true readiness:local

tf-init: ## terraform init for $(TF_DIR) using infra/terraform/backend.$(ENV).hcl
	cd $(TF_DIR) && terraform init -backend-config=../backend.$(ENV).hcl

tf-plan: ## terraform plan with envs/$(ENV).tfvars
	cd $(TF_DIR) && terraform plan -var-file=envs/$(ENV).tfvars

tf-apply: ## terraform apply with envs/$(ENV).tfvars
	cd $(TF_DIR) && terraform apply -var-file=envs/$(ENV).tfvars

.PHONY: help setup lint fmt test policy secrets-scan check tracker catalog demo serve docker-build docker-run tf-init tf-plan tf-apply
