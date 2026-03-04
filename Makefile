PYTHON ?= python3
VENV_DIR ?= .venv
VENV_PYTHON := $(VENV_DIR)/bin/python
REQ_FILE ?= requirements.txt
REQ_STAMP := $(VENV_DIR)/.requirements.stamp

APP ?= app.main:app
HOST ?= 127.0.0.1
PORT ?= 18080

.PHONY: run setup clean help

help:
	@echo "Targets:"
	@echo "  make run    - Auto check env, install deps if needed, then start server"
	@echo "  make setup  - Auto check env and install deps if needed"
	@echo "  make clean  - Remove virtual environment"

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
