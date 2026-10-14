.PHONY: data evidence test build-test hover-test page-data pipeline

# Raw data into GEO_DATA_DIR (see .env); resumable
data:
	python scripts/acquire_public_data.py opencellid boundaries overture population ookla

# Evidence table for every cited paper (rule R2)
evidence:
	python scripts/evidence.py

test:
	python -m pytest -q tests

build-test:
	cd tests/browser && (test -d node_modules/puppeteer-core || npm i --no-save puppeteer-core@23) && node build_test.js $(CURDIR)/docs/build.html /tmp | grep -E "FAIL|build-page checks"

hover-test:
	cd tests/browser && (test -d node_modules/puppeteer-core || npm i --no-save puppeteer-core@23) && mkdir -p /tmp/geo1-shots && node hover_test.js $(CURDIR)/docs/index.html /tmp/geo1-shots

page-data:
	python scripts/export_page_data.py

# Full pipeline (needs GEO_DATA_DIR from .env): P0 grid → P1 gap → P2 speed model → ADR-005 noise follow-up → page data
pipeline:
	python scripts/build_hex_table.py
	python scripts/experience_gap.py
	python scripts/speed_model.py
	python scripts/noise_followup.py
	python scripts/noise_validation.py
	python scripts/new_site_effect.py
	python scripts/new_site_diagnostics.py
	python scripts/export_page_data.py
