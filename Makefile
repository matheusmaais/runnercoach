.PHONY: test ingest analyze recommend dashboard pipeline

GARMIN ?= data/raw/garmin/Activities.csv

test:
	pytest -q

ingest:
	python scripts/ingest_garmin.py --garmin "$(GARMIN)"

analyze:
	python scripts/run_pipeline.py --garmin "$(GARMIN)" --analyze-only

recommend:
	python scripts/run_pipeline.py --garmin "$(GARMIN)" --after-workout

dashboard:
	python scripts/build_dashboard.py

pipeline:
	python scripts/run_pipeline.py --garmin "$(GARMIN)" --after-workout
