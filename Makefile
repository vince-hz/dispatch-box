PYTHON ?= python3
VENV_DIR ?= .venv
VENV_PYTHON := $(VENV_DIR)/bin/python
REQ_FILE ?= requirements.txt
REQ_STAMP := $(VENV_DIR)/.requirements.stamp

APP ?= app.main:app
HOST ?= 127.0.0.1
PORT ?= 18080

DOCKER_TAG ?=
DOCKER_PUSH ?= 1
DOCKER_LATEST ?= 1
DOCKER_PLATFORMS ?= linux/amd64,linux/arm64
DOCKER_CONTEXT ?= .
DOCKERFILE ?= Dockerfile

DOCKER_TAG_FROM_GOAL :=
DOCKER_RELEASE_EXTRA_ARGS :=

ifeq ($(firstword $(MAKECMDGOALS)),docker-release)
DOCKER_TAG_FROM_GOAL := $(word 2,$(MAKECMDGOALS))
DOCKER_RELEASE_ARGS := $(wordlist 2,$(words $(MAKECMDGOALS)),$(MAKECMDGOALS))
DOCKER_RELEASE_EXTRA_ARGS := $(wordlist 3,$(words $(MAKECMDGOALS)),$(MAKECMDGOALS))
ifneq ($(strip $(DOCKER_RELEASE_ARGS)),)
.PHONY: $(DOCKER_RELEASE_ARGS)
$(DOCKER_RELEASE_ARGS):
	@:
endif
endif

.PHONY: run setup clean help docker-release

help:
	@echo "Targets:"
	@echo "  make run    - Auto check env, install deps if needed, then start server"
	@echo "  make setup  - Auto check env and install deps if needed"
	@echo "  make clean  - Remove virtual environment"
	@echo "  make docker-release [vX.Y.Z] - Build Docker image and optionally push it"

setup:
	@command -v $(PYTHON) >/dev/null 2>&1 || (echo "Error: '$(PYTHON)' not found in PATH."; exit 1)
	@if [ ! -x "$(VENV_PYTHON)" ]; then \
		echo "Creating virtual environment: $(VENV_DIR)"; \
		$(PYTHON) -m venv $(VENV_DIR); \
	fi
	@if [ ! -f "$(REQ_STAMP)" ] || [ "$(REQ_FILE)" -nt "$(REQ_STAMP)" ]; then \
		echo "Installing dependencies from $(REQ_FILE)"; \
		$(VENV_PYTHON) -m pip install -r $(REQ_FILE); \
		touch $(REQ_STAMP); \
	else \
		echo "Dependencies are up to date."; \
	fi

run: setup
	$(VENV_PYTHON) -m uvicorn $(APP) --reload --host $(HOST) --port $(PORT)

clean:
	rm -rf $(VENV_DIR)

docker-release:
	@if [ -n "$(strip $(DOCKER_RELEASE_EXTRA_ARGS))" ]; then \
		echo "Usage: make docker-release [vX.Y.Z] [DOCKER_PUSH=0] [DOCKER_LATEST=0] [DOCKER_PLATFORMS=linux/amd64,linux/arm64]"; \
		exit 1; \
	fi
	@TAG_VALUE="$(DOCKER_TAG)"; \
	if [ -z "$$TAG_VALUE" ]; then TAG_VALUE="$(DOCKER_TAG_FROM_GOAL)"; fi; \
	IMAGE="vincehz/dispatch-box" \
	TAG="$$TAG_VALUE" \
	PUSH="$(DOCKER_PUSH)" \
	LATEST="$(DOCKER_LATEST)" \
	PLATFORMS="$(DOCKER_PLATFORMS)" \
	CONTEXT="$(DOCKER_CONTEXT)" \
	DOCKERFILE="$(DOCKERFILE)" \
	./scripts/docker-release.sh
