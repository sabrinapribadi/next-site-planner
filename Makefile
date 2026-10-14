.PHONY: data evidence test build-test hover-test page-data pipeline

# Environments live outside OneDrive (shared by all portfolio projects; rebuild with `make env`)
PY ?= $(HOME)/.venvs/portfolio/bin/python
NODE_DIR ?= $(HOME)/.portfolio-node

env:
	uv venv $(HOME)/.venvs/portfolio --python 3.12 --allow-existing && VIRTUAL_ENV=$(HOME)/.venvs/portfolio uv pip install -r requirements.txt
	mkdir -p $(NODE_DIR) && cd $(NODE_DIR) && (test -f package.json || echo '{"name": "portfolio-node", "private": true}' > package.json) && npm i -q puppeteer-core@23

# Raw data into GEO_DATA_DIR (see .env); resumable
data:
	$(PY) scripts/acquire_public_data.py opencellid boundaries overture population worldpop ghsl ookla

# Evidence table for every cited paper (rule R2)
evidence:
	$(PY) scripts/evidence.py

test:
	$(PY) -m pytest -q tests

build-test:
	cd tests/browser && NODE_PATH=$(NODE_DIR)/node_modules node build_test.js $(CURDIR)/docs/build.html /tmp | grep -E "FAIL|build-page checks"

hover-test:
	cd tests/browser && mkdir -p /tmp/geo1-shots && NODE_PATH=$(NODE_DIR)/node_modules node hover_test.js $(CURDIR)/docs/index.html /tmp/geo1-shots

page-data:
	$(PY) scripts/export_page_data.py

# Full pipeline (needs GEO_DATA_DIR from .env): P0 grid → P1 gap → P2 speed model → noise follow-up → P3 new-site effect
# → P4 site plan → nominal validation (WorldPop, WorldCover, Copernicus DEM; ADR-008 amendment 1) → page data
pipeline:
	$(PY) scripts/build_hex_table.py
	$(PY) scripts/experience_gap.py
	$(PY) scripts/speed_model.py
	$(PY) scripts/noise_followup.py
	$(PY) scripts/noise_validation.py
	$(PY) scripts/new_site_effect.py
	$(PY) scripts/new_site_diagnostics.py
	$(PY) scripts/new_site_crossing_checks.py
	$(PY) scripts/new_site_crossing_checks.py --estimand capacity
	$(PY) scripts/worldpop_hex.py
	$(PY) scripts/population_crosscheck.py
	$(PY) scripts/degurba_check.py
	$(PY) scripts/site_plan.py
	cp data/outputs/p4_site_plan.json data/outputs/p4_site_plan_original.json
	mkdir -p data/outputs/p4_original_plans && cp docs/data/plans/*.csv data/outputs/p4_original_plans/
	$(PY) scripts/site_plan.py --validated
	$(PY) scripts/nominal_validation_report.py
	$(PY) scripts/export_page_data.py
