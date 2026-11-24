"""Z08: run equivalent analytical queries in DuckDB and ClickHouse.

Windows 10: py -3.11 pz8/scripts/compare_engines.py
Connects to ClickHouse through docker exec (HTTP default user may require a password).
Never modifies existing data or schemas.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import re
import subprocess
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
DB_FILE = ROOT / "pz3" / "retail_local.duckdb"
SQL_DIR = ROOT / "pz8" / "sql"
DUCK_SQL = ROOT / "pz4" / "sql" / "analytics.sql"
DUCK_METRIC = ROOT / "pz4" / "sql" / "canonical_metric.sql"
OUT = ROOT / "pz8" / "checks" / "results.md"
CONTAINER = "olap_clickhouse"


def run_ch(sql: str, *, output: str = "JSON") -> str:
    cmd = ["docker", "exec", "-i", CONTAINER, "clickhouse-client", f"--format={output}", "--query", sql]
    result = subprocess.run(cmd, capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(f"ClickHouse error ({result.returncode}): " + result.stderr.decode("utf-8", "replace"))
    return result.stdout.decode("utf-8", "replace").strip()


def statements(filename: Path) -> list[str]:
    raw = filename.read_text(encoding="utf-8-sig")
    no_comments = "\n".join(line.split("--", 1)[0] for line in raw.splitlines())
    return [s.strip() for s in no_comments.split(";") if s.strip()]


def normalize(value):
    if value is None:
        return None
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        return Decimal(str(value)).quantize(Decimal("0.01"))
    if isinstance(value, str) and re.fullmatch(r"[+-]?\d+(?:\.\d+)?", value):
        return Decimal(value).quantize(Decimal("0.01"))
    return str(value)


def value_str(x):
    return "NULL" if x is None else str(x)


def md_table(columns, rows):
    def esc(v):
        return value_str(v).replace("|", "\\|").replace("\n", " ")
    return "\n".join([
        "| " + " | ".join(map(esc, columns)) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
        *["| " + " | ".join(esc(v) for v in row) + " |" for row in rows],
    ])


def run():
    if not DB_FILE.is_file():
        raise FileNotFoundError(f"Missing DuckDB file: {DB_FILE}; run Z05 first")
    names = ("canonical metric", "Q1 slice", "Q2 monthly roll-up", "Q2b yearly roll-up", "Q3 dice", "Q4 window", "Q5 top-N")
    duck_queries = statements(DUCK_METRIC) + statements(DUCK_SQL)
    ch_queries = statements(SQL_DIR / "canonical_metric_clickhouse.sql") + statements(SQL_DIR / "analytics_clickhouse.sql")
    if len(duck_queries) != 7 or len(ch_queries) != 7:
        raise ValueError(f"Expected metric + 6 queries; got DuckDB={len(duck_queries)}, CH={len(ch_queries)}")
    con = duckdb.connect(str(DB_FILE), read_only=True)
    report = ["# Z08 — ClickHouse vs DuckDB: результаты сверки", "", "**Студент:** Лежень А.В.  ", "**Группа:** 233  ", "**Домен:** D1 — Розница  ", f"**Дата UTC:** {datetime.now(timezone.utc).isoformat(timespec='seconds')}", "", "**Источники:** DuckDB `pz3/retail_local.duckdb` и ClickHouse `retail_pz7` (одинаковая витрина).", ""]
    try:
        for title, duck_sql, ch_sql in zip(names, duck_queries, ch_queries):
            duck_cursor = con.execute(duck_sql)
            duck_columns = [c[0] for c in duck_cursor.description]
            duck_rows = [tuple(row) for row in duck_cursor.fetchall()]
            ch_response = json.loads(run_ch(ch_sql))
            ch_columns = [m["name"] for m in ch_response["meta"]]
            ch_rows = [tuple(row[name] for name in ch_columns) for row in ch_response["data"]]
            if duck_columns != ch_columns:
                raise AssertionError(f"{title}: column mismatch: DuckDB {duck_columns} vs CH {ch_columns}")
            duck_normal = sorted(tuple(normalize(v) for v in r) for r in duck_rows)
            ch_normal = sorted(tuple(normalize(v) for v in r) for r in ch_rows)
            if duck_normal != ch_normal:
                raise AssertionError(f"{title}: DuckDB {duck_rows} != ClickHouse {ch_rows}")
            print(f"PASS {title}: {len(duck_rows)} rows match")
            report.extend([f"## {title} — MATCH", "", md_table(duck_columns, duck_rows), ""])
        metric = con.execute(duck_queries[0]).fetchone()[0]
        if Decimal(str(metric)) != Decimal("264.00"):
            raise AssertionError(f"Unexpected sample revenue {metric} (expected 264.00)")
        report.extend(["## ORDER BY: фильтр по ведущему полю", "", "`fact_sales` хранится в ClickHouse с `ORDER BY (date_id, store_id, product_id)`. Эксперимент фильтрует по `date_id = 20240101`.", ""])
        duck_filter = con.execute("SELECT count() AS rows_for_date, SUM(amount) AS revenue_for_date FROM fact_sales WHERE date_id = 20240101").fetchone()
        ch_filter_obj = json.loads(run_ch("SELECT count() AS rows_for_date, sum(amount) AS revenue_for_date FROM retail_pz7.fact_sales WHERE date_id = 20240101"))
        row = ch_filter_obj["data"][0]
        ch_filter = (row["rows_for_date"], row["revenue_for_date"])
        if tuple(map(normalize, duck_filter)) != tuple(map(normalize, ch_filter)):
            raise AssertionError(f"Leading ORDER BY filter differs: {duck_filter} vs {ch_filter}")
        report.extend([md_table(["Система", "Строк за дату", "Выручка за дату"], [("DuckDB", *duck_filter), ("ClickHouse", *ch_filter)]), ""])
        print(f"PASS filtered date_id=20240101: count={duck_filter[0]} sum={duck_filter[1]}")
        try:
            plan = run_ch("EXPLAIN indexes = 1 SELECT count() FROM retail_pz7.fact_sales WHERE date_id = 20240101", output="TabSeparatedRaw")
            report.extend(["### EXPLAIN indexes = 1 (ClickHouse)", "", "```text", plan, "```", ""])
            print("PASS ClickHouse EXPLAIN indexes=1")
        except RuntimeError as exc:
            report.extend(["EXPLAIN не поддержан в данной конфигурации; результат фильтрации и выбор ключа показаны выше.", "", f"Ошибка: `{str(exc).splitlines()[0]}`", ""])
            print("NOTE: EXPLAIN could not be captured; this is optional")
        report.extend(["## Вывод", "", "Все шесть запросов из З04 и эталон `SUM(amount)` вернули одинаковые данные в DuckDB и ClickHouse. Эталон на sample равен **264.00**. Фильтр по ведущему полю `date_id` также даёт одинаковый результат. `ORDER BY` задаёт порядок хранения и индекс разреженного типа, **но не обеспечивает уникальность**. На 15 строках ускорение не измеряем. Месячное `PARTITION BY` сознательно не используется: слишком мелкие партиции не дают пользы на sample; решение и цена отказа описаны в `notes/partition_decision.md` и добавлении в `pz2/cut.md`.", ""])
    finally:
        con.close()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(report), encoding="utf-8")
    print(f"PASS: report saved to {OUT}")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print("FAIL:", exc, file=sys.stderr)
        sys.exit(1)
