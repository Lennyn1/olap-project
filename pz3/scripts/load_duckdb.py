"""Reproducible Z03 DuckDB load from ../Стенд/data/raw/*.csv.
Run from any directory: py -3.11 pz3/scripts/load_duckdb.py
"""
from __future__ import annotations

from pathlib import Path
import os
import tempfile
import duckdb

PROJECT = Path(__file__).resolve().parents[2]
PZ3 = PROJECT / "pz3"
RAW = PROJECT / "Стенд" / "data" / "raw"
DATABASE = PZ3 / "retail_local.duckdb"
DDL = PZ3 / "sql" / "ddl_duckdb.sql"
OUT = PZ3 / "checks" / "results.md"

FILES = ("dim_date.csv", "dim_store.csv", "dim_product.csv", "fact_sales.csv")


def csv_source(con: duckdb.DuckDBPyConnection, filename: str) -> str:
    """Return an escaped SQL literal for a UTF-8 CSV path."""
    path = (RAW / filename).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Missing source: {path}")
    return "'" + str(path).replace("'", "''") + "'"


def main() -> None:
    for filename in FILES:
        if not (RAW / filename).is_file():
            raise FileNotFoundError(f"Copy the source CSV into {RAW}: {filename}")
    PZ3.mkdir(parents=True, exist_ok=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    # Build an entirely new database to avoid DELETE + FK limitations in DuckDB.
    # Replace the previous database only after successful loading and checks.
    fd, temporary_name = tempfile.mkstemp(prefix="retail_build_", suffix=".duckdb", dir=PZ3)
    os.close(fd)
    Path(temporary_name).unlink()  # DuckDB creates its own new database file.
    con = None
    try:
        con = duckdb.connect(temporary_name)
        con.execute(DDL.read_text(encoding="utf-8"))
        con.execute("BEGIN TRANSACTION")
        try:
            con.execute(f"""INSERT INTO dim_date
                SELECT CAST(date_id AS INTEGER), CAST(full_date AS DATE),
                       CAST(year AS SMALLINT), CAST(month AS TINYINT),
                       month_name, CAST(day_of_week AS TINYINT)
                FROM read_csv({csv_source(con, 'dim_date.csv')}, header=true, all_varchar=true)""")
            con.execute(f"""INSERT INTO dim_store
                SELECT CAST(store_id AS INTEGER), store_name, city, region
                FROM read_csv({csv_source(con, 'dim_store.csv')}, header=true, all_varchar=true)""")
            con.execute(f"""INSERT INTO dim_product
                SELECT CAST(product_id AS INTEGER), product_name, category, brand
                FROM read_csv({csv_source(con, 'dim_product.csv')}, header=true, all_varchar=true)""")
            con.execute(f"""INSERT INTO fact_sales
                SELECT CAST(sale_id AS BIGINT), CAST(date_id AS INTEGER),
                       CAST(store_id AS INTEGER), CAST(product_id AS INTEGER),
                       CAST(qty AS INTEGER), CAST(amount AS DECIMAL(12,2))
                FROM read_csv({csv_source(con, 'fact_sales.csv')}, header=true, all_varchar=true)""")
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise

        counts = {
            name: con.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
            for name in ("dim_date", "dim_store", "dim_product", "fact_sales")
        }
        revenue, quantity = con.execute(
            "SELECT SUM(amount), SUM(qty) FROM fact_sales"
        ).fetchone()
        null_keys = con.execute("""SELECT COUNT(*) FROM fact_sales
            WHERE sale_id IS NULL OR date_id IS NULL
               OR store_id IS NULL OR product_id IS NULL""").fetchone()[0]
        orphans = {}
        for label, dim, key in (
            ("dates", "dim_date", "date_id"),
            ("stores", "dim_store", "store_id"),
            ("products", "dim_product", "product_id"),
        ):
            orphans[label] = con.execute(f"""SELECT COUNT(*)
                FROM fact_sales f LEFT JOIN {dim} d ON f.{key}=d.{key}
                WHERE d.{key} IS NULL""").fetchone()[0]
        for name, value in counts.items():
            print(f"{name}: {value}")
        print(f"total_revenue: {revenue}")
        print(f"total_quantity: {quantity}")
        print(f"null_fact_keys: {null_keys}")
        for label, value in orphans.items():
            print(f"orphan_{label}: {value}")

        # Validate the provided sample exactly; do not report success for a bad load.
        expected = {"dim_date": 8, "dim_store": 5, "dim_product": 8, "fact_sales": 15}
        if counts != expected or str(revenue) != "264.00" or null_keys or any(orphans.values()):
            raise RuntimeError("Verification failed: counts, revenue, null keys, or FKs differ")
        rows = [
            "# З03 — Результаты проверок DuckDB", "",
            "**Студент:** Лежень А.В.  ", "**Группа:** 233  ",
            "**Домен:** D1 — Розница  ",
            "**База:** `pz3/retail_local.duckdb`  ", "",
            "## Число строк", "",
            "| Таблица | Строк |", "|---|---:|",
        ]
        rows.extend(f"| `{name}` | {value} |" for name, value in counts.items())
        rows.extend(["", "## Меры и контроль качества", "",
                     f"- `SUM(amount)` = **{revenue}** условных денежных единиц.",
                     f"- `SUM(qty)` = **{quantity}** единиц товара.",
                     f"- Пустых ключей факта = **{null_keys}**."])
        rows.extend(f"- Сирот FK ({label}) = **{value}**." for label, value in orphans.items())
        rows.extend(["", "## Повторный запуск", "",
                     "Загрузка создаёт новую временную базу, проверяет данные и заменяет прежний файл БД только при успехе. Повторный запуск не удваивает строки.",
                     "", "Проверка выполнена скриптом `pz3/scripts/load_duckdb.py`.", ""])
        # Close the temporary database before replacing on Windows.
        con.close()
        con = None
        os.replace(temporary_name, DATABASE)
        OUT.write_text("\n".join(rows), encoding="utf-8")
        print(f"OK: saved checks to {OUT}")
    finally:
        if con is not None:
            con.close()
        Path(temporary_name).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
