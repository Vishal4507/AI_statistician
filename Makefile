PY := python3
export PYTHONPATH := src

# Credentials live in .env (gitignored), not in a shell profile.  This machine's
# ~/.bash_profile is root-owned, so the usual export line cannot be written
# there; keeping the key project-local is cleaner anyway -- it is scoped to this
# project and disappears when the directory does.
-include .env
export

.PHONY: help setup data benchmark validate test eval eval-naive check-key smoke eval-live pilot analyze report demo clean-results all

help:
	@echo "AI Statistician"
	@echo "  make setup      install dependencies"
	@echo "  make data       download and freeze the four UCI datasets"
	@echo "  make benchmark  build all 64 case packages"
	@echo "  make validate   run the case validator"
	@echo "  make test       run the full test suite"
	@echo "  make eval       offline calibration run (432 runs, no API key)"
	@echo "  make eval-naive naive-policy floor"
	@echo "  make check-key  confirm the key is loaded (prints presence, never the value)"
	@echo "  make smoke      validate the live path with a few cents of API calls"
	@echo "  make eval-live  the live held-out experiment (needs ANTHROPIC_API_KEY)"
	@echo "  make pilot      two-tier headroom check (run BEFORE freezing prompts)"
	@echo "  make analyze    rebuild every result table from raw logs"
	@echo "  make report     regenerate the capstone results document"
	@echo "  make demo       launch the Streamlit demo"
	@echo "  make all        data -> benchmark -> validate -> test -> eval -> analyze"

setup:
	pip install -r requirements.txt

data:
	$(PY) scripts/acquire_data.py

benchmark:
	$(PY) scripts/build_benchmark.py

validate:
	$(PY) -c "import sys; sys.path.insert(0,'src'); \
	from aistat.benchmark.validator import validate_all; import json; \
	r=validate_all(); print(json.dumps({k:v for k,v in r.items() if k!='case_errors'}, indent=2)); \
	sys.exit(0 if r['passed'] else 1)"

test:
	$(PY) -m pytest tests/ -q

eval:
	$(PY) scripts/run_evaluation.py --client rulebased --split heldout --reps 3 --workers 6

eval-naive:
	$(PY) scripts/run_evaluation.py --client rulebased-naive --split heldout --reps 3 --workers 6

check-key:
	@$(PY) -c "import os,sys; sys.path.insert(0,'src'); \
	from aistat.agents.llm import api_key_available; \
	k=os.environ.get('ANTHROPIC_API_KEY',''); \
	print('key present:', bool(k), '| length:', len(k), \
	'| SDK sees it:', api_key_available())"

smoke: check-key
	$(PY) scripts/smoke_live.py

eval-live: smoke
	$(PY) scripts/run_evaluation.py --client anthropic --split heldout --reps 3 --workers 4

pilot:
	$(PY) scripts/pilot.py

analyze:
	$(PY) scripts/analyze.py --name heldout_rulebased_expert --quiet
	$(PY) scripts/analyze.py --name heldout_rulebased_naive --quiet || true
	$(PY) scripts/analyze.py --name heldout_rulebased_expert

report:
	$(PY) scripts/write_report.py --name heldout_rulebased_expert

demo:
	$(PY) -m streamlit run app/streamlit_app.py

clean-results:
	rm -f results/*.jsonl results/*_manifest.json reports/*.csv reports/*_results.json

all: data benchmark validate test eval analyze report
