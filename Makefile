# Recall — developer convenience targets.
# Usage: make <target>   (requires GNU make; on Windows use Git Bash or WSL)

PY ?= python3

.PHONY: help install dev test smoke doctor lint clean

help:           ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

install:        ## Install Recall with the MCP extra (editable)
	$(PY) -m pip install -e ".[mcp]"

dev:            ## Install with mcp + dev extras (for tests)
	$(PY) -m pip install -e ".[mcp,dev]"

test:           ## Run the test suite
	$(PY) -m pytest

smoke:          ## Run a quick end-to-end CLI smoke test in an isolated KB
	@RECALL_HOME=$$(mktemp -d) bash -c '\
	  recall init && \
	  printf "### Decision   Smoke entry." | recall append --workstream demo/test --title hello --session s1 --body - && \
	  recall index && \
	  recall search "smoke entry" --workstream demo/test'

doctor:         ## Diagnose sqlite-vec / Ollama / paths
	recall doctor

clean:          ## Remove caches and build artifacts
	rm -rf .pytest_cache **/__pycache__ build dist *.egg-info
