.PHONY: data evidence test

# Raw data into GEO_DATA_DIR (see .env); resumable
data:
	python scripts/acquire_public_data.py opencellid boundaries overture population ookla

# Evidence table for every cited paper (rule R2)
evidence:
	python scripts/evidence.py

test:
	pytest -q tests

build-test:
	cd tests/browser && (test -d node_modules/puppeteer-core || npm i --no-save puppeteer-core@23) && node build_test.js $(CURDIR)/docs/build.html /tmp | grep -E "FAIL|build-page checks"
