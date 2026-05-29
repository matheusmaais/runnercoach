.PHONY: test ingest analyze recommend dashboard pipeline

GARMIN ?= data/raw/garmin/Activities.csv
PYTHON ?= python3

test:
	$(PYTHON) -m pytest -q

ingest:
	$(PYTHON) scripts/ingest_garmin.py --garmin "$(GARMIN)"

analyze:
	$(PYTHON) scripts/run_pipeline.py --garmin "$(GARMIN)" --analyze-only

recommend:
	$(PYTHON) scripts/run_pipeline.py --garmin "$(GARMIN)" --after-workout

dashboard:
	$(PYTHON) scripts/build_dashboard.py

pipeline:
	$(PYTHON) scripts/run_pipeline.py --garmin "$(GARMIN)" --after-workout
