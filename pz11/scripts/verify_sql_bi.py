#!/usr/bin/env python3
"""Z11: compare actual ClickHouse revenue with manually observed Metabase card values.

Works on Windows with the existing Docker container; does not need HTTP credentials.
All comparisons are exact decimal (two decimal places). No guessed BI values.
"""
from __future__ import annotations

import argparse
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = ROOT / "sql"
RESULT = ROOT / "checks" / "results.md"


def run_clickhouse(sql_file: str) -> Decimal:
    sql = (SQL_DIR / sql_file).read_text(encoding="utf-8")
    cmd = ["docker", "exec", "-i", "olap_clickhouse", "clickhouse-client", "--format=TabSeparatedRaw"]
    proc = subprocess.run(cmd, input=sql, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(f"ClickHouse query {sql_file} failed: {proc.stderr.strip()}")
    values = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    if len(values) != 1:
        raise RuntimeError(f"Expected a single value from {sql_file}, got {values!r}")
    return parse_amount(values[0])


def parse_amount(value: str) -> Decimal:
    try:
        amount = Decimal(value.strip().replace("\u00a0", "").replace(" ", "").replace(",", "."))
        if not amount.is_finite():
            raise ValueError("Non-finite amount")
        return amount.quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Not a valid monetary value: {value!r}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Z11: compare ClickHouse and Metabase values")
    parser.add_argument("--bi-all", help="Number displayed by Metabase with date filter cleared, e.g. 264")
    parser.add_argument("--bi-jan", help="Number displayed by Metabase filtered Jan 1-31, 2024")
    args = parser.parse_args()

    all_sql = run_clickhouse("canonical_metric.sql")
    jan_sql = run_clickhouse("revenue_january_2024.sql")
    rows = [
        ("Весь период; фильтр даты сброшен; прочие фильтры отсутствуют", all_sql, args.bi_all),
        ("01.01.2024–31.01.2024 включительно; прочие фильтры отсутствуют", jan_sql, args.bi_jan),
    ]
    print(f"ClickHouse / all dates: {all_sql:.2f}")
    print(f"ClickHouse / January 2024: {jan_sql:.2f}")
    print("Source: retail_pz7.fact_sales; metric SUM(amount)")

    lines = [
        "# З11 — протокол сверки SQL и Metabase",
        "",
        "**Студент:** Лежень А.В. · **Группа:** 233",
        "**Проект:** D1 — Розница / Анализ розничных продаж",
        f"**Дата формирования протокола:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (локальное время)",
        "**ClickHouse:** retail_pz7.fact_sales (детальная таблица)",
        "**Metabase:** карточка «Общая выручка» из З10 (Native SQL с Field Filter `period`)",
        "**Метрика:** SUM(amount), единицы валюты не определены; Decimal(12,2); сравнение по двум десятичным знакам без допуска.",
        "",
        "| Условия фильтра | A: ClickHouse | B: Metabase | Итог |",
        "|---|---:|---:|---|",
    ]
    any_pending = False
    mismatch = False
    for desc, a, b_text in rows:
        if b_text is None:
            any_pending = True
            b_fmt = "Не введено"
            status = "Ожидает ручной проверки"
            print(f"PENDING BI value: {desc}")
        else:
            b = parse_amount(b_text)
            b_fmt = f"{b:.2f}"
            status = "PASS" if a == b else "FAIL"
            mismatch |= status == "FAIL"
            print(f"{status}: SQL={a:.2f}; BI={b:.2f}; {desc}")
        lines.append(f"| {desc} | {a:.2f} | {b_fmt} | {status} |")
    lines += [
        "",
        "## Вывод",
        (
            "**FAIL:** хотя бы одно число отличается. Проверьте фильтр, источник данных, SQL и формат числа."
            if mismatch else
            "**ПРОВЕРКА НЕ ЗАВЕРШЕНА:** заполните реальные значения с карточки Metabase через аргументы скрипта."
            if any_pending else
            "**PASS:** SQL и карточка Metabase показывают одну и ту же выручку при одинаковых фильтрах."
        ),
        "",
        "Эталон остаётся в `pz11/sql/canonical_metric.sql` и считается по детальной таблице; агрегат З09 не заменяет канон.",
        "",
        "## Способ проверки",
        "",
        "1. Открыть дашборд З10, убедиться, что дополнительные фильтры не заданы.",
        "2. Сбросить фильтр периода, переписать реальное число с карточки как `--bi-all`.",
        "3. Установить период с 01.01.2024 по 31.01.2024 включительно; переписать число как `--bi-jan`.",
        "4. Запустить скрипт с этими значениями повторно; сохранить этот протокол и при желании скриншот.",
    ]
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Report: {RESULT}")
    return 1 if mismatch else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, ValueError, FileNotFoundError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
