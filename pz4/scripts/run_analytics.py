"""Execute Z04 queries on the database created in Z03.
Run: py -3.11 pz4/scripts/run_analytics.py
"""
from pathlib import Path
from decimal import Decimal
import duckdb

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "pz3" / "retail_local.duckdb"
SQLDIR = ROOT / "pz4" / "sql"
OUT = ROOT / "pz4" / "checks" / "results.md"

def md_table(columns, rows):
    def esc(v):
        return str(v if v is not None else "NULL").replace("|", "\\|").replace("\n", " ")
    return "\n".join(["| " + " | ".join(columns) + " |",
                      "| " + " | ".join(["---"] * len(columns)) + " |"] +
                     ["| " + " | ".join(map(esc, row)) + " |" for row in rows])

def main():
    if not DB.is_file():
        raise FileNotFoundError(f"Нет базы {DB}. Сначала запустите З03: py -3.11 pz3/scripts/load_duckdb.py")
    con = duckdb.connect(str(DB), read_only=True)
    try:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        required = {"dim_date", "dim_store", "dim_product", "fact_sales"}
        if not required.issubset(tables):
            raise RuntimeError(f"Отсутствуют таблицы: {required - tables}")
        canonical = (SQLDIR / "canonical_metric.sql").read_text(encoding="utf-8")
        metric = con.execute(canonical).fetchone()[0]
        if metric is None:
            raise RuntimeError("Главная метрика NULL: пустая таблица фактов")
        print(f"canonical total_revenue: {metric}")
        # Validation specific to the unchanged sample. Real data may have another result.
        if metric != Decimal("264.00"):
            raise AssertionError(f"Для sample ожидается 264.00, получено {metric}")
        raw = (SQLDIR / "analytics.sql").read_text(encoding="utf-8")
        # SQL script contains no semicolons inside strings or comments.
        sql_without_comments = "\n".join(line for line in raw.splitlines() if not line.lstrip().startswith("--"))
        statements = [x.strip() for x in sql_without_comments.split(";") if x.strip()]
        if len(statements) < 6:
            raise RuntimeError(f"Ожидалось 6 запросов (включая два уровня roll-up), найдено {len(statements)}")
        report = ["# З04 — Результаты аналитических SQL-запросов", "", "**Студент:** Лежень А.В.  ", "**Группа:** 233  ",
                  "**Домен:** D1 — Розница  ", f"**База:** `pz3/retail_local.duckdb`  ", "", 
                  "## Эталонная метрика", "", f"`total_revenue = {metric}` условных денежных единиц.", ""]
        for n, sql in enumerate(statements, start=1):
            res = con.execute(sql)
            cols = [d[0] for d in res.description]
            rows = res.fetchall()
            print(f"Query {n}: {len(rows)} rows")
            report.extend([f"## Query {n}", "", md_table(cols, rows), ""])
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text("\n".join(report), encoding="utf-8")
        print(f"OK: results saved to {OUT}")
    finally:
        con.close()

if __name__ == "__main__":
    main()
