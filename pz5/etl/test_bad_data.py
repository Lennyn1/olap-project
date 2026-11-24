"""Negative check: damaged fact qty must stop P05 and leave the real database untouched.
Run: py -3.11 pz5/etl/test_bad_data.py
"""
from __future__ import annotations

import csv
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "Стенд" / "data" / "raw"
LOADER = ROOT / "pz5" / "etl" / "load.py"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="z05_negative_") as temp_dir:
        work = Path(temp_dir)
        damaged = work / "raw"
        damaged.mkdir()
        for file in RAW.glob("*.csv"):
            shutil.copy2(file, damaged / file.name)
        csv_path = damaged / "fact_sales.csv"
        with csv_path.open("r", encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        if not rows:
            raise RuntimeError("No fact rows to corrupt")
        rows[0]["qty"] = "-1"
        with csv_path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        fake_db = work / "test.duckdb"
        result = subprocess.run([sys.executable, str(LOADER),
                                 "--raw-dir", str(damaged),
                                 "--database", str(fake_db),
                                 "--log", str(work / "bad_run_log.md")],
                                capture_output=True, text=True, encoding="utf-8", errors="replace")
        print(result.stdout)
        print(result.stderr)
        if result.returncode == 0 or fake_db.exists():
            print("FAIL: invalid input was accepted")
            return 1
        if "Quality check failed" not in result.stderr:
            print("FAIL: load failed for an unrelated reason")
            return 1
        print("PASS: invalid qty rejected, no test database published; real files unchanged")
        return 0


if __name__ == "__main__":
    sys.exit(main())
