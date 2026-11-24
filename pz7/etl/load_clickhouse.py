"""Z07: reproducible raw CSV -> ClickHouse MergeTree, compared with DuckDB.

Run from any directory: py -3.11 pz7/etl/load_clickhouse.py
Needs running Docker ClickHouse on localhost:8123 and Z03/05 DuckDB file.
Rebuilds ONLY the dedicated retail_pz7 database on every run.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from decimal import Decimal
import os
from pathlib import Path
import sys
import subprocess

import duckdb

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "Стенд" / "data" / "raw"
DUCKDB = ROOT / "pz3" / "retail_local.duckdb"
DDL = ROOT / "pz7" / "sql" / "ddl_clickhouse.sql"
RESULTS = ROOT / "pz7" / "checks" / "results.md"
CONTAINER = os.environ.get("CLICKHOUSE_CONTAINER", "olap_clickhouse")
DB = "retail_pz7"
TABLES = ("dim_date", "dim_store", "dim_product", "fact_sales")


def ch(query: str, data: bytes | None = None) -> str:
    """Run SQL via the locally working ClickHouse client inside Docker.

    For INSERT ... FORMAT CSVWithNames, pipe the CSV bytes to the client stdin.
    No HTTP password reset or credentials in the repository are required.
    """
    command = ["docker", "exec", "-i", CONTAINER, "clickhouse-client", "--query", query]
    try:
        result = subprocess.run(command, input=data, capture_output=True, check=False)
    except FileNotFoundError as exc:
        raise RuntimeError("docker not found in PATH; start Docker Desktop and check installation") from exc
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"ClickHouse command failed (exit {result.returncode}): {message}")
    return result.stdout.decode("utf-8", errors="replace").strip()


def scalar(query: str) -> str:
    result = ch(query + " FORMAT TabSeparated")
    if "\n" in result or "\t" in result:
        raise RuntimeError(f"Expected scalar response: {result}")
    return result


def source_counts() -> dict[str, int]:
    counts = {}
    for table in TABLES:
        path = RAW / (table + ".csv")
        if not path.is_file():
            raise FileNotFoundError(f"Raw CSV missing: {path}")
        with path.open(encoding="utf-8-sig", newline="") as fh:
            rows = csv.DictReader(fh)
            expected = {"dim_date": {"date_id", "full_date", "year", "month", "month_name", "day_of_week"},
                        "dim_store": {"store_id", "store_name", "city", "region"},
                        "dim_product": {"product_id", "product_name", "category", "brand"},
                        "fact_sales": {"sale_id", "date_id", "store_id", "product_id", "qty", "amount"}}[table]
            if set(rows.fieldnames or []) != expected:
                raise ValueError(f"Unexpected columns in {path}: {rows.fieldnames}")
            counts[table] = sum(1 for _ in rows)
    return counts


def duckdb_baseline() -> tuple[dict[str, int], Decimal]:
    if not DUCKDB.is_file():
        raise FileNotFoundError(f"DuckDB missing: {DUCKDB}; run Z05 first")
    con = duckdb.connect(str(DUCKDB), read_only=True)
    try:
        counts = {t: int(con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]) for t in TABLES}
        revenue = con.execute("SELECT SUM(amount) AS total_revenue FROM fact_sales").fetchone()[0]
        if revenue is None:
            raise ValueError("DuckDB fact_sales is empty")
        return counts, Decimal(str(revenue))
    finally:
        con.close()


def parse_ddl(path: Path) -> list[str]:
    """Remove SQL line comments before splitting statements by semicolon."""
    sql = path.read_text(encoding="utf-8-sig")
    sql_without_comments = "\n".join(
        line.split("--", 1)[0]
        for line in sql.splitlines()
    )
    return [part.strip() for part in sql_without_comments.split(";") if part.strip()]


def build() -> None:
    raw_counts = source_counts()
    duck_counts, duck_revenue = duckdb_baseline()
    print("DuckDB:", duck_counts, "total_revenue=", duck_revenue)
    if raw_counts != duck_counts:
        raise ValueError(f"CSV counts differ from DuckDB: CSV={raw_counts}; DuckDB={duck_counts}. Run Z05 first")
    if not DDL.is_file():
        raise FileNotFoundError(DDL)

    print("ClickHouse ping:", ch("SELECT 'Ok.'"))
    # P07 full-refresh: only the dedicated demo namespace is rebuilt.
    # A failure during rebuild can leave it incomplete; rerun after fixing the cause.
    ch(f"DROP DATABASE IF EXISTS {DB} SYNC")
    for ddl in parse_ddl(DDL):
        ch(ddl)
    print(f"DDL: created MergeTree tables in {DB}")

    for table in TABLES:  # dimensions first, then fact
        payload = (RAW / f"{table}.csv").read_bytes()
        ch(f"INSERT INTO {DB}.{table} FORMAT CSVWithNames", payload)
        print(f"Loaded {table}: {raw_counts[table]} CSV rows")

    result_counts = {t: int(scalar(f"SELECT count() FROM {DB}.{t}")) for t in TABLES}
    result_revenue = Decimal(scalar(f"SELECT sum(amount) FROM {DB}.fact_sales"))
    print("ClickHouse:", result_counts, "total_revenue=", result_revenue)
    if result_counts != duck_counts or result_revenue != duck_revenue:
        raise ValueError(f"Mismatch: DuckDB {duck_counts}/{duck_revenue}, ClickHouse {result_counts}/{result_revenue}")
    # Additional direct tests: no duplicate sale IDs or orphan FK in ClickHouse.
    dup = int(scalar(f"SELECT count() - uniqExact(sale_id) FROM {DB}.fact_sales"))
    orphans = {}
    for name, key in (("date", "date_id"), ("store", "store_id"), ("product", "product_id")):
        orphans[name] = int(scalar(f"SELECT count() FROM {DB}.fact_sales AS f LEFT JOIN {DB}.dim_{name} AS d ON f.{key}=d.{key} WHERE d.{key}=0"))
    if dup or any(orphans.values()):
        raise ValueError(f"Data integrity failed: duplicate_sale_ids={dup}, orphan_FK={orphans}")

    lines = ["# Z07 — DuckDB ↔ ClickHouse reconciliation", "",
             "Студент: Лежень А.В. · группа 233 · домен D1 «Розница»", "",
             f"Дата проверки (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}", "",
             "| Table | DuckDB | ClickHouse | Match |", "|---|---:|---:|---|"]
    for table in TABLES:
        lines.append(f"| `{table}` | {duck_counts[table]} | {result_counts[table]} | YES |")
    lines += ["", f"**Canonical total_revenue (SUM(amount)): DuckDB {duck_revenue:.2f}; ClickHouse {result_revenue:.2f}; MATCH.**", "",
              f"Duplicate sale IDs: {dup}; orphan FK: {orphans}", "",
              "Full refresh: each run recreates only `retail_pz7`. Repeating the command must keep counts and revenue unchanged.", ""]
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    # Append a section for each run, so both attempts are demonstrable.
    with RESULTS.open("a", encoding="utf-8") as out:
        if RESULTS.stat().st_size:
            out.write("\n---\n\n")
        out.write("\n".join(lines))
    print(f"PASS: DuckDB and ClickHouse match; results appended to {RESULTS}")


if __name__ == "__main__":
    try:
        build()
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
