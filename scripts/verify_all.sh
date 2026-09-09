#!/usr/bin/env bash
# Definition-of-done check (blueprint section 12).
# Reproduces the benchmark and the result tables from documented commands.
set -e
cd "$(dirname "$0")/.."
export PYTHONPATH=src

echo "=== 1/8  benchmark builds and validates ==="
python3 scripts/build_benchmark.py | tail -3

echo ""
echo "=== 2/8  test suite ==="
python3 -m pytest tests/ -q 2>&1 | tail -2

echo ""
echo "=== 3/8  offline evaluation (432 runs) ==="
rm -f results/heldout_rulebased_expert*
python3 scripts/run_evaluation.py --client rulebased --split heldout --reps 3 --workers 6 2>&1 | tail -2

echo ""
echo "=== 4/8  result tables rebuild from logs ==="
python3 scripts/analyze.py --name heldout_rulebased_expert --quiet && echo "  tables regenerated"

echo ""
echo "=== 5/8  capstone report regenerates ==="
python3 scripts/write_report.py --name heldout_rulebased_expert

echo ""
echo "=== 6/8  label audit ==="
python3 scripts/audit_labels.py | tail -4

echo ""
echo "=== 7/8  static site exports ==="
python3 scripts/export_site.py | tail -1

echo ""
echo "=== 8/8  demo boots ==="
python3 - <<'PY'
import os, subprocess, sys, time, urllib.request
env = dict(os.environ, STREAMLIT_SERVER_HEADLESS="true",
           STREAMLIT_BROWSER_GATHER_USAGE_STATS="false")
p = subprocess.Popen([sys.executable, "-m", "streamlit", "run",
                      "app/streamlit_app.py", "--server.port", "8901",
                      "--server.headless", "true"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
ok = False
for _ in range(30):
    time.sleep(1)
    try:
        if urllib.request.urlopen("http://localhost:8901/_stcore/health",
                                  timeout=2).status == 200:
            ok = True
            break
    except Exception:
        pass
p.terminate()
print("  demo health check:", "OK" if ok else "FAILED")
sys.exit(0 if ok else 1)
PY

echo ""
echo "ALL CHECKS PASSED"
