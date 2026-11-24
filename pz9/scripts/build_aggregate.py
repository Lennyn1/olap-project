"""Z09: rebuild day/store aggregate and verify it against detailed ClickHouse facts.

Windows: py -3.11 pz9/scripts/build_aggregate.py
Requires Docker Desktop + running olap_clickhouse with Z07's retail_pz7.
No HTTP credentials required: uses clickhouse-client via docker exec.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "pz9"
SQL = BASE / "sql"
OUT = BASE / "checks" / "results.md"
CONTAINER = os.environ.get("CLICKHOUSE_CONTAINER", "olap_clickhouse")
DB = "retail_pz7"
AGG = f"{DB}.agg_daily_store_sales"


def query(sql: str, fmt: str | None = "JSON") -> list[dict]:
    result = subprocess.run(
        ["docker", "exec", "-i", CONTAINER, "clickhouse-client", "--query", sql] + ([f"--format={fmt}"] if fmt else []),
        capture_output=True, check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", "replace").strip())
    if fmt == "JSON":
        return json.loads(result.stdout.decode("utf-8", "replace"))["data"]
    return []


def statements(path: Path) -> list[str]:
    raw = path.read_text(encoding="utf-8-sig")
    # Remove comments BEFORE splitting so a semicolon in a comment is harmless.
    no_comments = "\n".join(line.split("--", 1)[0] for line in raw.splitlines())
    return [s.strip() for s in no_comments.split(";") if s.strip()]


def value(obj, key):
    if key not in obj:
        raise ValueError(f"Missing result column: {key}; got {obj}")
    return obj[key]


def verify() -> tuple[int, Decimal, int, int]:
    fact = query(f"SELECT count() AS rows, sum(amount) AS revenue FROM {DB}.fact_sales")[0]
    agg = query(f"SELECT count() AS groups, sum(sales_rows) AS rows, sum(amount_sum) AS revenue FROM {AGG}")[0]
    fact_rows, agg_rows = int(fact["rows"]), int(agg["rows"] or 0)
    fact_revenue = Decimal(str(fact["revenue"]))
    agg_revenue = Decimal(str(agg["revenue"] or 0))
    groups = int(agg["groups"])
    if fact_rows <= 0 or groups <= 0:
        raise AssertionError("Fact or aggregate is empty")
    if (fact_rows, fact_revenue) != (agg_rows, agg_revenue):
        raise AssertionError(f"Count/revenue mismatch: fact={fact_rows}/{fact_revenue}, agg={agg_rows}/{agg_revenue}")
    # Also compare EVERY day+store slice, not just grand totals.
    raw_groups = query(f"""
      SELECT d.full_date AS sale_date, f.store_id AS store_id,
             sum(f.amount) AS revenue, sum(toInt64(f.qty)) AS qty, count() AS rows
      FROM {DB}.fact_sales f
      INNER JOIN {DB}.dim_date d ON d.date_id = f.date_id
      GROUP BY sale_date, store_id
      ORDER BY sale_date, store_id
    """)
    aggregate_groups = query(f"""
      SELECT sale_date, store_id, amount_sum AS revenue, qty_sum AS qty, sales_rows AS rows
      FROM {AGG} ORDER BY sale_date, store_id
    """)

    def normalize(rows):
        return [
            (str(r["sale_date"]), int(r["store_id"]), Decimal(str(r["revenue"])),
             int(r["qty"]), int(r["rows"]))
            for r in rows
        ]

    if normalize(raw_groups) != normalize(aggregate_groups):
        raise AssertionError(f"Day/store aggregation mismatch: detail={raw_groups} agg={aggregate_groups}")
    # Control month: January 2024, same date conditions on both sides.
    january_fact = Decimal(str(query(f"""
      SELECT sum(f.amount) AS revenue FROM {DB}.fact_sales f
      JOIN {DB}.dim_date d ON f.date_id=d.date_id
      WHERE d.full_date >= '2024-01-01' AND d.full_date < '2024-02-01'
    """)[0]["revenue"] or 0))
    january_agg = Decimal(str(query(f"""
      SELECT sum(amount_sum) AS revenue FROM {AGG}
      WHERE sale_date >= '2024-01-01' AND sale_date < '2024-02-01'
    """)[0]["revenue"] or 0))
    if january_fact != january_agg:
        raise AssertionError(f"January mismatch: fact={january_fact}, agg={january_agg}")
    return fact_rows, fact_revenue, groups, len(raw_groups)


def main() -> None:
    # Protect the detailed source, which is already populated by Z07.
    fact_rows = int(query(f"SELECT count() AS rows FROM {DB}.fact_sales")[0]["rows"])
    if not fact_rows:
        raise ValueError("Z07 fact_sales is empty; run Z07 loader first")
    for path in (SQL / "ddl_aggregate.sql", SQL / "refresh_aggregate.sql"):
        for statement in statements(path):
            query(statement, fmt=None)
    fact_rows, fact_revenue, groups, matched = verify()
    print(f"PASS fact_sales: count={fact_rows} total_revenue={fact_revenue:.2f}")
    print(f"PASS aggregate: groups={groups} covered_sales={fact_rows} total_revenue={fact_revenue:.2f}")
    print(f"PASS: all {matched} day x store groups match; January 2024 matches")
    print("PASS: aggregate rebuilt (TRUNCATE + INSERT SELECT), no accumulation on rerun")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "## Successful aggregate refresh", "",
        f"- UTC: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"- Detail fact: **{fact_rows}** rows, canonical `SUM(amount)` = **{fact_revenue:.2f}**",
        f"- Aggregate: **{groups}** day × store rows; covers **{fact_rows}** facts",
        f"- Day × store groups verified: **{matched}**",
        "- January 2024 revenue: **MATCH**", "- Full dataset revenue: **MATCH**",
        "- Refresh: **TRUNCATE aggregate, then INSERT SELECT from fact**", "",
    ]
    if not OUT.exists() or not OUT.read_text(encoding="utf-8").strip():
        OUT.write_text("# Z09 — Aggregate build and checks\n\n**Лежень А.В. · группа 233 · D1 Розница**\n\n" + "\n".join(lines), encoding="utf-8")
    else:
        with OUT.open("a", encoding="utf-8") as fh:
            fh.write("\n---\n\n" + "\n".join(lines))
    print(f"OK: results appended to {OUT}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
