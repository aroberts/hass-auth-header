.SHELLFLAGS += -x -e
.ONESHELL:
PY_SOURCES = custom_components scripts tests
HASS_VERSION = $(shell pip freeze | grep \^homeassistant | sed 's/==/\n/g' | tail -n 1)
TEST_HA ?= latest
TEST_HARNESS ?= latest
TEST_PYTHON ?= 3.14
COMPOSE_ARGS = -f scripts/docker-compose.yml -p hass-auth-header

all: lint-fix lint

lint-fix:
	isort $(PY_SOURCES)
	black $(PY_SOURCES)
	ruff $(PY_SOURCES)

# Same install and run steps as one CI row, e.g.
# make test TEST_HA=2024.6.4 TEST_HARNESS=0.13.136 TEST_PYTHON=3.12 TEST_EXTRA='josepy<2'
test:
	uv venv -q --clear -p $(TEST_PYTHON) .venv
	VIRTUAL_ENV=.venv scripts/ci_install.sh $(TEST_HARNESS) $(TEST_HA) $(foreach req,$(TEST_EXTRA),'$(req)')
	.venv/bin/python scripts/run_tests.py

lint:
	pylint $(PY_SOURCES)

test-env-start:
	VERSION=${HASS_VERSION} docker-compose $(COMPOSE_ARGS)  up -d

test-env-stop:
	VERSION=${HASS_VERSION} docker compose $(COMPOSE_ARGS) down

test-env-remove:
	VERSION=${HASS_VERSION} docker compose $(COMPOSE_ARGS) down -v

hass-restart:
	docker-compose $(COMPOSE_ARGS) exec homeassistant killall -HUP python3
