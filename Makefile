export PYTHONPATH := $(CURDIR)/airflow:$(CURDIR)/airflow/helpers:$(CURDIR)/airflow/plugins

COMPOSE ?= docker compose -f docker/docker-compose.yml

AIRFLOW_SERVICE ?= airflow
AIRFLOW_LOCAL_DB_HOST ?= postgres
AIRFLOW_LOCAL_DB_NAME ?= postgres
AIRFLOW_LOCAL_DB_USER ?= postgres
AIRFLOW_LOCAL_DB_PASSWORD ?= postgres
AIRFLOW_LOCAL_DB_PORT ?= 5432

install:
	@echo "Instalando dependências..."
	uv sync --all-extras --group dev

requirements:
	@echo "Gerando requirements.txt (apenas dependências de runtime)..."
	uv export --no-dev --no-hashes --no-annotate --no-header --format requirements-txt -o requirements.txt

setup:
	@echo "Configurando ambiente..."
	@if ! command -v uv >/dev/null 2>&1; then \
		echo "uv não encontrado. Instale antes: https://docs.astral.sh/uv/getting-started/installation/"; \
		exit 1; \
	fi
	@if [ ! -f .env ]; then \
		if [ -f local.env ]; then \
			cp local.env .env; \
			echo ".env criado a partir de local.env"; \
		else \
			echo "local.env não encontrado. Crie o .env manualmente."; \
			exit 1; \
		fi; \
	fi
	$(MAKE) install
	$(MAKE) requirements
	bash setup-git-hooks.sh

format:
	uv run black .
	uv run ruff check --fix .
	uv run sqlfmt .

lint:
	uv run black . --check
	uv run ruff check .
	uv run ty check .
	uv run sqlfmt . --check

test:
	uv run pytest tests/unit --junitxml=report.xml --cov=. --cov-report=xml:coverage.xml

test-integration:
	@if [ ! -f .env ]; then cp local.env .env; echo ".env created from local.env"; fi
	@$(COMPOSE) --env-file local.env up -d minio minio-init postgres
	@echo "Waiting for services to be healthy..."
	@$(COMPOSE) --env-file local.env ps
	uv run pytest tests/integration/ -m integration -v

compose:
	@echo "Iniciando ambiente local do Airflow com Docker Compose..."
	@if [ ! -f .env ]; then cp local.env .env; echo ".env criado a partir de local.env"; fi
	$(COMPOSE) --env-file .env up -d --build
	$(MAKE) dev
	$(MAKE) dev-check

dev:
	@$(COMPOSE) ps --status running $(AIRFLOW_SERVICE) >/dev/null 2>&1 || (echo "Serviço '$(AIRFLOW_SERVICE)' não está em execução. Rode: make compose" && exit 1)
	@echo "Aguardando Airflow/DB ficarem prontos..."
	@$(COMPOSE) exec -T $(AIRFLOW_SERVICE) sh -c 'for i in $$(seq 1 30); do airflow db migrate >/dev/null 2>&1 && exit 0; sleep 2; done; echo "Airflow DB não ficou pronto a tempo para inicializar."; exit 1'
	@$(COMPOSE) exec -T $(AIRFLOW_SERVICE) airflow variables set dynamic_schedules '{}'
	@$(COMPOSE) exec -T $(AIRFLOW_SERVICE) sh -c "printf '%s\n' '{\"postgres_default\":{\"conn_type\":\"postgres\",\"host\":\"$(AIRFLOW_LOCAL_DB_HOST)\",\"schema\":\"$(AIRFLOW_LOCAL_DB_NAME)\",\"login\":\"$(AIRFLOW_LOCAL_DB_USER)\",\"password\":\"$(AIRFLOW_LOCAL_DB_PASSWORD)\",\"port\":$(AIRFLOW_LOCAL_DB_PORT)}}' > /tmp/airflow-connections.json && airflow connections import --overwrite /tmp/airflow-connections.json && rm -f /tmp/airflow-connections.json"
	@echo "Ambiente local do Airflow configurado com sucesso."

dev-check:
	@$(COMPOSE) ps --status running $(AIRFLOW_SERVICE) >/dev/null 2>&1 || (echo "Serviço '$(AIRFLOW_SERVICE)' não está em execução. Rode: make compose" && exit 1)
	@$(COMPOSE) exec -T $(AIRFLOW_SERVICE) airflow variables get dynamic_schedules >/dev/null
	@$(COMPOSE) exec -T $(AIRFLOW_SERVICE) airflow connections get postgres_default >/dev/null
	@echo "Validação concluída: variables e connection do Airflow estão configuradas."

.PHONY: install requirements setup format lint test test-integration compose dev dev-check
