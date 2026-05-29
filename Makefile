.PHONY: test ingest analyze recommend dashboard pipeline coach frontend-data frontend-build frontend

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

coach:
	$(PYTHON) scripts/generate_recommendation.py

frontend-data:
	$(PYTHON) scripts/build_frontend_data.py

frontend-build: frontend-data
	cd web && npm install && npm run build

frontend: frontend-build
