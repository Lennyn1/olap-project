"""Z05: repeatable raw -> staging -> DuckDB star model, with fail-fast checks.

Windows: py -3.11 pz5/etl/load.py
Optional: --raw-dir PATH --database PATH --log PATH
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import os
import tempfile
import sys

import duckdb

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RAW = ROOT / "Стенд" / "data" / "raw"
DEFAULT_DB = ROOT / "pz3" / "retail_local.duckdb"
DEFAULT_LOG = ROOT / "pz5" / "checks" / "run_log.md"
DDL = ROOT / "pz3" / "sql" / "ddl_duckdb.sql"
TABLES = ("dim_date", "dim_store", "dim_product", "fact_sales")


def sql_path(path: Path) -> str:
    return "'" + str(path.resolve()).replace("'", "''") + "'"


def scalar(conn, query: str) -> int:
    return int(conn.execute(query).fetchone()[0])


def verify(conn, condition: str, label: str) -> None:
    failures = scalar(conn, f"SELECT COUNT(*) FROM ({condition}) AS violations")
    print(f"CHECK {label}: {failures} violations")
    if failures:
        raise ValueError(f"Quality check failed: {label} ({failures} violations)")


def snapshot(db: Path) -> dict[str, str]:
    if not db.exists():
        return {"fact_count": "not created", "total_revenue": "not created"}
    conn = duckdb.connect(str(db), read_only=True)
    try:
        count = conn.execute("SELECT COUNT(*) FROM fact_sales").fetchone()[0]
        revenue = conn.execute("SELECT SUM(amount) FROM fact_sales").fetchone()[0]
        return {"fact_count": str(count), "total_revenue": str(revenue)}
    finally:
        conn.close()


def append_log(log: Path, lines: list[str]) -> None:
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as output:
        if log.stat().st_size == 0:
            output.write("# З05 — журнал ELT\n\nСтудент: Лежень А.В. · группа 233 · домен D1 «Розница»\n\n")
        output.write("\n".join(lines) + "\n\n")


def build(raw: Path, db: Path, log: Path) -> None:
    for table in TABLES:
        source = raw / f"{table}.csv"
        if not source.is_file():
            raise FileNotFoundError(f"Missing CSV: {source}")
    if not DDL.is_file():
        raise FileNotFoundError(f"Missing DDL: {DDL}")
    db.parent.mkdir(parents=True, exist_ok=True)
    before = snapshot(db)
    print(f"BEFORE fact_sales={before['fact_count']} total_revenue={before['total_revenue']}")

    # A new DB is the full-refresh staging area. Old database stays intact on check failure.
    fd, temp_name = tempfile.mkstemp(prefix="z05_build_", suffix=".duckdb", dir=str(db.parent))
    os.close(fd)
    temp = Path(temp_name)
    temp.unlink()
    conn = None
    try:
        conn = duckdb.connect(str(temp))
        for table in TABLES:
            # All varchar in staging: reject malformed values in checks, not with CSV auto inference.
            conn.execute(f"CREATE TEMP TABLE stg_{table} AS SELECT * FROM read_csv({sql_path(raw / (table + '.csv'))}, header=true, all_varchar=true)")
        print("STAGING: four CSV files loaded into stg_* tables")

        # Check 1: missing required fields (including blank CSV values).
        required = {
            "dim_date": ("date_id", "full_date", "year", "month", "month_name", "day_of_week"),
            "dim_store": ("store_id", "store_name", "city", "region"),
            "dim_product": ("product_id", "product_name", "category", "brand"),
            "fact_sales": ("sale_id", "date_id", "store_id", "product_id", "qty", "amount"),
        }
        for table, columns in required.items():
            where = " OR ".join(f"{column} IS NULL OR length(trim({column})) = 0" for column in columns)
            verify(conn, f"SELECT 1 FROM stg_{table} WHERE {where}", f"null_or_blank/{table}")

        # Check 2: domain / range, invalid numeric casts and nonsensical dates.
        verify(conn, """SELECT 1 FROM stg_dim_date WHERE
          TRY_CAST(date_id AS INTEGER) IS NULL OR TRY_CAST(full_date AS DATE) IS NULL
          OR TRY_CAST(full_date AS DATE) < DATE '2000-01-01'
          OR TRY_CAST(full_date AS DATE) > DATE '2100-12-31'
          OR TRY_CAST(year AS INTEGER) IS NULL OR TRY_CAST(month AS INTEGER) NOT BETWEEN 1 AND 12
          OR TRY_CAST(day_of_week AS INTEGER) NOT BETWEEN 1 AND 7
          OR TRY_CAST(year AS INTEGER) != YEAR(TRY_CAST(full_date AS DATE))
          OR TRY_CAST(month AS INTEGER) != MONTH(TRY_CAST(full_date AS DATE))""", "range/dates")
        for table, key in (("dim_store", "store_id"), ("dim_product", "product_id")):
            verify(conn, f"SELECT 1 FROM stg_{table} WHERE TRY_CAST({key} AS INTEGER) IS NULL OR TRY_CAST({key} AS INTEGER) <= 0", f"range/{table}")
        verify(conn, """SELECT 1 FROM stg_fact_sales WHERE
            TRY_CAST(sale_id AS BIGINT) IS NULL OR TRY_CAST(sale_id AS BIGINT) <= 0
            OR TRY_CAST(date_id AS INTEGER) IS NULL
            OR TRY_CAST(store_id AS INTEGER) IS NULL OR TRY_CAST(store_id AS INTEGER) <= 0
            OR TRY_CAST(product_id AS INTEGER) IS NULL OR TRY_CAST(product_id AS INTEGER) <= 0
            OR TRY_CAST(qty AS INTEGER) IS NULL OR TRY_CAST(qty AS INTEGER) < 0
            OR TRY_CAST(amount AS DECIMAL(12,2)) IS NULL
            OR TRY_CAST(amount AS DECIMAL(12,2)) < 0""", "range/fact_sales")

        # Check 3: duplicate business keys. sale_id is the unique source event ID.
        for table, key in (("dim_date", "date_id"), ("dim_store", "store_id"),
                           ("dim_product", "product_id"), ("fact_sales", "sale_id")):
            verify(conn, f"SELECT {key} FROM stg_{table} GROUP BY {key} HAVING COUNT(*) > 1", f"duplicate/{table}")

        # Check 4: orphan references, verified against raw staging, before inserts.
        for table, key in (("dim_date", "date_id"), ("dim_store", "store_id"), ("dim_product", "product_id")):
            verify(conn, f"""SELECT f.sale_id FROM stg_fact_sales AS f
               LEFT JOIN stg_{table} AS d ON f.{key} = d.{key}
               WHERE d.{key} IS NULL""", f"orphan/{key}")

        # Fresh schema and ordered inserts: all dimensions first, fact last.
        conn.execute(DDL.read_text(encoding="utf-8"))
        conn.execute("BEGIN TRANSACTION")
        try:
            conn.execute("""INSERT INTO dim_date
                SELECT CAST(date_id AS INTEGER), CAST(full_date AS DATE),
                       CAST(year AS SMALLINT), CAST(month AS TINYINT), month_name,
                       CAST(day_of_week AS TINYINT) FROM stg_dim_date""")
            conn.execute("""INSERT INTO dim_store
                SELECT CAST(store_id AS INTEGER), store_name, city, region FROM stg_dim_store""")
            conn.execute("""INSERT INTO dim_product
                SELECT CAST(product_id AS INTEGER), product_name, category, brand FROM stg_dim_product""")
            conn.execute("""INSERT INTO fact_sales
                SELECT CAST(sale_id AS BIGINT), CAST(date_id AS INTEGER),
                       CAST(store_id AS INTEGER), CAST(product_id AS INTEGER),
                       CAST(qty AS INTEGER), CAST(amount AS DECIMAL(12,2)) FROM stg_fact_sales""")
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

        counts = {t: scalar(conn, f"SELECT COUNT(*) FROM {t}") for t in TABLES}
        revenue = conn.execute("SELECT SUM(amount) FROM fact_sales").fetchone()[0]
        if any(counts[t] != scalar(conn, f"SELECT COUNT(*) FROM stg_{t}") for t in TABLES):
            raise ValueError("Loaded row count differs from staging")
        print("AFTER " + " ".join(f"{k}={v}" for k,v in counts.items()) + f" total_revenue={revenue}")
        if counts["fact_sales"] == 0 or revenue is None:
            raise ValueError("Empty fact or missing revenue")
        # Close both the connection and all temporary objects before replace on Windows.
        conn.close()
        conn = None
        os.replace(temp, db)
        after = snapshot(db)
        append_log(log, [f"## Успешный запуск · {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
                         f"- До: count = {before['fact_count']}, SUM(amount) = {before['total_revenue']}",
                         f"- После: count = {after['fact_count']}, SUM(amount) = {after['total_revenue']}",
                         "- Строки по таблицам: " + ", ".join(f"{k}={v}" for k,v in counts.items()),
                         "- Checks: null, range, duplicates, FK — 0 нарушений", "- Статус: PASS"])
        print(f"PASS: log appended to {log}")
    finally:
        if conn is not None:
            conn.close()
        temp.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="P05 validated full refresh, DuckDB")
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW)
    parser.add_argument("--database", type=Path, default=DEFAULT_DB)
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    args = parser.parse_args()
    try:
        build(args.raw_dir.resolve(), args.database.resolve(), args.log.resolve())
    except Exception as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
