"""Read-only Z10 prerequisites check. Uses docker exec, not host HTTP auth.
Run: py -3.11 pz10/scripts/check_data.py
"""
from pathlib import Path
import subprocess
import sys
from decimal import Decimal, InvalidOperation

BASE = Path(__file__).resolve().parents[1]


def query(sql):
    proc = subprocess.run(
        ["docker", "exec", "olap_clickhouse", "clickhouse-client",
         "--format=TabSeparated", "--query", sql],
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if proc.returncode:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())
    return proc.stdout.strip()


def main():
    checks = [
        ("fact rows and canonical revenue", "SELECT count(), sum(amount) FROM retail_pz7.fact_sales"),
        ("aggregate rows and revenue", "SELECT count(), sum(amount_sum) FROM retail_pz7.agg_daily_store_sales"),
        ("revenue by region", "SELECT s.region, sum(f.amount) FROM retail_pz7.fact_sales f JOIN retail_pz7.dim_store s ON f.store_id=s.store_id GROUP BY s.region ORDER BY s.region"),
        ("revenue by category", "SELECT p.category, sum(f.amount) FROM retail_pz7.fact_sales f JOIN retail_pz7.dim_product p ON f.product_id=p.product_id GROUP BY p.category ORDER BY p.category"),
    ]
    report = ["# З10 — подготовка данных для Metabase", "", "Студент: Лежень А.В., группа 233.", "", "Источник: ClickHouse `retail_pz7`. Проверка доступности из Metabase проводится отдельно.", ""]
    outputs = {}
    for title, sql in checks:
        value = query(sql)
        print(f"{title}: {value}")
        outputs[title] = value
        report.extend([f"## {title}", "", "```text", value, "```", ""])
    fact = outputs[checks[0][0]].split("\t")
    agg = outputs[checks[1][0]].split("\t")
    if len(fact) != 2 or len(agg) != 2:
        raise ValueError("Unexpected ClickHouse output format")
    try:
        fact_count, fact_revenue = int(fact[0]), Decimal(fact[1])
        agg_count, agg_revenue = int(agg[0]), Decimal(agg[1])
    except (ValueError, InvalidOperation) as exc:
        raise ValueError(f"Unexpected numeric values: fact={fact}, aggregate={agg}") from exc
    if fact_count != 15 or fact_revenue != Decimal("264.00"):
        raise ValueError(f"Unexpected canonical fact result: {fact}")
    if agg_count < 1:
        raise ValueError("Aggregate contains no rows")
    if agg_revenue != fact_revenue:
        raise ValueError(f"Aggregate revenue differs: {agg_revenue} vs {fact_revenue}")
    report.extend(["**PASS:** fact contains 15 rows, fact/aggregate revenue is 264.00.", "", "Важно: этот скрипт НЕ создаёт виджеты в Metabase и НЕ проверяет фильтр дашборда. Проверки интерфейса — вручную по README.", ""])
    out = BASE / "checks" / "results.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(report), encoding="utf-8")
    print("PASS: ClickHouse fact/aggregate match; results saved:", out)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, FileNotFoundError) as exc:
        print("FAIL:", exc, file=sys.stderr)
        sys.exit(1)
