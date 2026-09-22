# port5g — build targets. Run `make help` for a list.
PY ?= python3
SEED ?= 20260915

.PHONY: help install test figures assumptions run check-assumptions clean lint

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install:  ## Editable install with dev extras
	$(PY) -m pip install -e ".[dev]"

test:  ## Run pytest including the §4 numeric anchors
	$(PY) -m pytest -q

run:  ## Run the full config -> results pipeline (results/results.json)
	$(PY) -m port5g.cli run --seed $(SEED)

figures: run  ## Regenerate every figure from results (deterministic)
	$(PY) -m port5g.cli figures

assumptions:  ## Regenerate docs/assumptions.md from the config provenance annotations
	$(PY) -m port5g.cli assumptions

check-assumptions:  ## Fail if any config value is still [UNVERIFIED] (use before final report)
	$(PY) -m port5g.cli assumptions --strict

lint:
	ruff check src tests

clean:
	rm -rf figures/*.png results/*.json .pytest_cache

