.PHONY: help test lint validate check install-local zip
PY ?= python3

help: ## List targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

test: ## Run the full test suite once (no watch mode)
	$(PY) -m unittest discover -s tests
	node --test tests/cli.test.mjs

lint: ## Shellcheck the shell scripts and byte-compile the Python
	$(if $(wildcard scripts/*.sh),shellcheck -S warning $(wildcard scripts/*.sh),@echo 'no shell scripts')
	$(PY) -m py_compile $(wildcard scripts/*.py)

validate: ## Validate the plugin manifest, skills, agents and hooks
	claude plugin validate . --strict

check: lint test validate ## Everything CI runs

install-local: ## Load this checkout as a plugin for one session: claude --plugin-dir .
	@echo "Run: claude --plugin-dir $(CURDIR)"

zip: ## Build one Claude.ai upload zip per skill into dist/
	node cli/tmn-fdekit.mjs zip --out dist
