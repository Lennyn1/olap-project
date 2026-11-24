#!/usr/bin/env python3
"""Z12 non-destructive local ClickHouse/DuckDB integration checks.

Run: py -3.11 pz12/scripts/check_contour.py
Does not modify ClickHouse or Metabase. The Metabase UI check remains manual.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import csv
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'pz12' / 'checks' / 'results.md'
CH_CONTAINER = os.environ.get('CLICKHOUSE_CONTAINER', 'olap_clickhouse')
DB = 'retail_pz7'
TABLES = ('dim_date', 'dim_store', 'dim_product', 'fact_sales')
EXPECTED = {'dim_date': 8, 'dim_store': 5, 'dim_product': 8, 'fact_sales': 15}
BASELINE = Decimal('264.00')


def ch(sql: str) -> str:
    result = subprocess.run(
        ['docker', 'exec', CH_CONTAINER, 'clickhouse-client', '--format=TabSeparatedRaw', '--query', sql],
        capture_output=True, text=True, encoding='utf-8', errors='replace', check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or f'Docker/ClickHouse exit code {result.returncode}')
    return result.stdout.strip()


def check() -> list[tuple[str, bool, str]]:
    items: list[tuple[str, bool, str]] = []

    def record(label: str, passed: bool, details: str) -> None:
        items.append((label, passed, details))
        print(('PASS' if passed else 'FAIL') + ' ' + label + ': ' + details)

    raw = ROOT / 'Стенд' / 'data' / 'raw'
    counts = {}
    for table in TABLES:
        file = raw / (table + '.csv')
        try:
            with file.open(encoding='utf-8-sig', newline='') as fh:
                counts[table] = sum(1 for _ in csv.DictReader(fh))
            record('raw ' + table, counts[table] == EXPECTED[table], f'{counts[table]} rows')
        except Exception as exc:
            record('raw ' + table, False, str(exc))

    duckfile = ROOT / 'pz3' / 'retail_local.duckdb'
    try:
        import duckdb
        with duckdb.connect(str(duckfile), read_only=True) as conn:
            fact_count, fact_sum = conn.execute('SELECT count(*), sum(amount) FROM fact_sales').fetchone()
        record('DuckDB', fact_count == 15 and Decimal(str(fact_sum)) == BASELINE,
               f'fact_sales={fact_count}, SUM(amount)={fact_sum}')
    except Exception as exc:
        record('DuckDB', False, f'{exc} (run Z05 before check)')

    try:
        actual = {}
        for table in TABLES:
            actual[table] = int(ch(f'SELECT count() FROM {DB}.{table}'))
            record('CH ' + table, actual[table] == EXPECTED[table], f'{actual[table]} rows')
        revenue = Decimal(ch(f'SELECT sum(amount) FROM {DB}.fact_sales'))
        record('CH canonical', revenue == BASELINE, f'SUM(amount)={revenue:.2f}')
        duplicates = int(ch(f'SELECT count() - uniqExact(sale_id) FROM {DB}.fact_sales'))
        record('CH duplicate sale_id', duplicates == 0, str(duplicates))
        # Ensure fact is MergeTree and uses the expected storage key.
        engine, sorting = ch(
            f"SELECT engine, sorting_key FROM system.tables WHERE database='{DB}' AND name='fact_sales'"
        ).split('\t', 1)
        record('CH fact MergeTree/order', engine == 'MergeTree' and 'date_id' in sorting and 'store_id' in sorting,
               f'engine={engine}, sorting_key={sorting}')
        groups_str, covered_str, agg_str = ch(
            f'SELECT count(), sum(sales_rows), sum(amount_sum) FROM {DB}.agg_daily_store_sales'
        ).split('\t')
        groups, covered, aggregate = int(groups_str), int(covered_str), Decimal(agg_str)
        record('CH aggregate', groups == 13 and covered == 15 and aggregate == revenue,
               f'groups={groups}, covered_sales={covered}, SUM(amount_sum)={aggregate:.2f}')
        jan_fact = Decimal(ch(
            f"SELECT sum(f.amount) FROM {DB}.fact_sales f JOIN {DB}.dim_date d ON f.date_id=d.date_id "
            "WHERE d.full_date >= '2024-01-01' AND d.full_date < '2024-02-01'"
        ))
        jan_agg = Decimal(ch(
            f"SELECT sum(amount_sum) FROM {DB}.agg_daily_store_sales "
            "WHERE sale_date >= '2024-01-01' AND sale_date < '2024-02-01'"
        ))
        record('CH January fact vs aggregate', jan_fact == jan_agg,
               f'fact={jan_fact:.2f}, aggregate={jan_agg:.2f}')
    except Exception as exc:
        record('ClickHouse contour', False, str(exc))

    for file in ('pz2/passport.md', 'pz2/cut.md', 'pz7/sql/ddl_clickhouse.sql',
                 'pz10/dashboards/01_total_revenue.sql', 'pz11/checks/results.md'):
        record('file ' + file, (ROOT / file).is_file(), 'present' if (ROOT / file).is_file() else 'missing')
    return items


def main() -> int:
    checks = check()
    ok = all(passed for _, passed, _ in checks)
    lines = [
        '# З12 — проверка зачётного контура', '',
        '**Лежень А.В. · группа 233 · D1 Розница**', '',
        '**Дата UTC:** ' + datetime.now(timezone.utc).isoformat(timespec='seconds'),
        '**Режим:** только чтение, без пересоздания БД', '',
        '| Проверка | Статус | Данные |', '|---|---|---|',
    ]
    for label, passed, detail in checks:
        detail = detail.replace('|', '\\|').replace('\n', ' ')
        lines.append(f'| {label} | {"PASS" if passed else "FAIL"} | {detail} |')
    lines += ['', '**Итог автоматических проверок:** ' + ('PASS' if ok else 'FAIL'), '',
              '**Metabase:** не проверяется скриптом. Нужна отдельная ручная проверка дашборда, SQL Native, общего фильтра и протокола З11.', '']
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text('\n'.join(lines), encoding='utf-8')
    print(('PASS' if ok else 'FAIL') + f': wrote {OUT}')
    return 0 if ok else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        raise SystemExit(1)
