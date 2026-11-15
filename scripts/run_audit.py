"""Run the full audit: every two-way table, the threshold sweep, differential privacy, figures,
reports/metrics.json and the dashboard's data file (web/public/tables.json).

    python scripts/download_data.py
    python scripts/run_audit.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from privaudit.audit import run  # noqa: E402

if __name__ == "__main__":
    m = run()
    print(json.dumps({k: v for k, v in m.items() if k not in ("k_sweep", "dp")}, indent=2))
