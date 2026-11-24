"""Z06 P06: reproducible, isolated SCD2 demo. Run: py -3.11 pz6/scripts/run_scd2.py

Uses read-only pz3 DuckDB star, builds pz6/scd2_demo.duckdb from scratch.
Simulates retroactive category change effective 2024-02-01 for product_id 101.
It never modifies pz3 database or raw CSV.
"""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'pz3' / 'retail_local.duckdb'
TARGET = ROOT / 'pz6' / 'scd2_demo.duckdb'
DDL = ROOT / 'pz6' / 'sql' / 'scd2_ddl.sql'
CHECK_SQL = ROOT / 'pz6' / 'sql' / 'checks.sql'
REPORT = ROOT / 'pz6' / 'checks' / 'results.md'
PRODUCT_ID = 101
BOUNDARY = date(2024, 2, 1)
NEW_CATEGORY = 'Свежее молоко'  # illustrative change, NOT present in the original CSV


def need(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def md_table(headers: list[str], rows: list[tuple]) -> str:
    def fmt(v):
        return 'NULL' if v is None else str(v)
    return '| ' + ' | '.join(headers) + ' |\n| ' + ' | '.join(['---'] * len(headers)) + ' |\n' + ''.join(
        '| ' + ' | '.join(fmt(v) for v in row) + ' |\n' for row in rows
    )


def main():
    if not SOURCE.is_file():
        raise FileNotFoundError(f'DuckDB from Z03 not found: {SOURCE}. Run pz5/etl/load.py first.')
    source = duckdb.connect(str(SOURCE), read_only=True)
    tmp = None
    dest = None
    try:
        original = {table: source.execute(f'SELECT * FROM {table}').fetchall()
                    for table in ('dim_date', 'dim_product', 'fact_sales')}
        date_columns = [row[0] for row in source.execute('DESCRIBE dim_date').fetchall()]
        product_columns = [row[0] for row in source.execute('DESCRIBE dim_product').fetchall()]
        sale_columns = [row[0] for row in source.execute('DESCRIBE fact_sales').fetchall()]
        dates = [dict(zip(date_columns, r)) for r in original['dim_date']]
        products = [dict(zip(product_columns, r)) for r in original['dim_product']]
        sales = [dict(zip(sale_columns, r)) for r in original['fact_sales']]
        date_lookup = {r['date_id']: r['full_date'] for r in dates}
        product_lookup = {r['product_id']: r for r in products}
        need(PRODUCT_ID in product_lookup, f'Product {PRODUCT_ID} absent from source')
        need(len(sales) > 0, 'No sales to demonstrate')
        need(all(r['product_id'] in product_lookup and r['date_id'] in date_lookup for r in sales),
             'Source contains missing product/date references')
        need(any(r['product_id'] == PRODUCT_ID and date_lookup[r['date_id']] < BOUNDARY for r in sales),
             'No historical sales of demo product before boundary')
        need(any(r['product_id'] == PRODUCT_ID and date_lookup[r['date_id']] >= BOUNDARY for r in sales),
             'No sales of demo product after boundary')

        def source_january():
            revenues = {}
            for sale in sales:
                if date(2024, 1, 1) <= date_lookup[sale['date_id']] < BOUNDARY:
                    category = product_lookup[sale['product_id']]['category']
                    revenues[category] = revenues.get(category, Decimal('0')) + sale['amount']
            return sorted(revenues.items())

        baseline_january = source_january()
        baseline_total = sum((r['amount'] for r in sales), Decimal('0'))
        old_category = product_lookup[PRODUCT_ID]['category']
        need(old_category != NEW_CATEGORY, 'New category must differ from old category')

        fd, filename = tempfile.mkstemp(prefix='z06_', suffix='.duckdb', dir=str(TARGET.parent))
        os.close(fd)
        tmp = Path(filename)
        tmp.unlink()
        dest = duckdb.connect(str(tmp))
        dest.execute(DDL.read_text(encoding='utf-8'))
        dest.execute('CREATE TABLE source_dates (date_id INTEGER PRIMARY KEY, full_date DATE NOT NULL)')
        dest.executemany('INSERT INTO source_dates VALUES (?, ?)',
                         [(r['date_id'], r['full_date']) for r in dates])

        # Initial state: every product has one current SCD2 version.
        for r in products:
            dest.execute('INSERT INTO dim_product_scd2 VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                         [r['product_id'] * 10 + 1, r['product_id'], r['product_name'], r['category'],
                          r['brand'], date(1900, 1, 1), None, True])

        initial_versions = dest.execute('SELECT COUNT(*) FROM dim_product_scd2 WHERE product_id = ?',
                                        [PRODUCT_ID]).fetchone()[0]
        need(initial_versions == 1, 'Expected one initial product version')

        # Simulated category change: close the original, retain its record, open a new one.
        dest.execute('''UPDATE dim_product_scd2 SET valid_to = ?, is_current = FALSE
                        WHERE product_id = ? AND is_current = TRUE''', [BOUNDARY, PRODUCT_ID])
        product = product_lookup[PRODUCT_ID]
        dest.execute('INSERT INTO dim_product_scd2 VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                     [PRODUCT_ID * 10 + 2, PRODUCT_ID, product['product_name'], NEW_CATEGORY,
                      product['brand'], BOUNDARY, None, True])

        # Facts carry the surrogate key of the correct version AS OF event date.
        for sale in sales:
            sale_date = date_lookup[sale['date_id']]
            match = dest.execute('''SELECT product_sk FROM dim_product_scd2
                WHERE product_id = ? AND valid_from <= ?
                  AND (valid_to IS NULL OR ? < valid_to)''',
                [sale['product_id'], sale_date, sale_date]).fetchall()
            need(len(match) == 1, f'Expected exactly one SCD version for sale {sale["sale_id"]}')
            dest.execute('INSERT INTO fact_sales_scd2 VALUES (?, ?, ?, ?, ?, ?)',
                         [sale['sale_id'], sale['date_id'], sale['store_id'], match[0][0],
                          sale['qty'], sale['amount']])

        versions = dest.execute('''SELECT product_sk, product_id, category, valid_from, valid_to,
                                          is_current FROM dim_product_scd2
                                   WHERE product_id = ? ORDER BY valid_from''', [PRODUCT_ID]).fetchall()
        links = dest.execute('''SELECT f.sale_id, d.full_date, p.product_sk, p.category, f.amount
                                FROM fact_sales_scd2 f
                                JOIN dim_product_scd2 p ON p.product_sk = f.product_sk
                                JOIN source_dates d ON d.date_id = f.date_id
                                WHERE p.product_id = ? ORDER BY d.full_date, f.sale_id''',
                             [PRODUCT_ID]).fetchall()
        after_january = dest.execute('''SELECT p.category, SUM(f.amount) AS revenue
            FROM fact_sales_scd2 f
            JOIN dim_product_scd2 p ON p.product_sk = f.product_sk
            JOIN source_dates d ON d.date_id = f.date_id
            WHERE d.full_date >= DATE '2024-01-01' AND d.full_date < DATE '2024-02-01'
            GROUP BY p.category ORDER BY p.category''').fetchall()
        counts = dest.execute('SELECT COUNT(*), SUM(amount) FROM fact_sales_scd2').fetchone()
        overlaps = dest.execute('''SELECT COUNT(*) FROM fact_sales_scd2 f
            JOIN dim_product_scd2 p ON f.product_sk = p.product_sk
            JOIN source_dates d ON f.date_id = d.date_id
            WHERE d.full_date < p.valid_from OR
                  (p.valid_to IS NOT NULL AND d.full_date >= p.valid_to)''').fetchone()[0]
        need(len(versions) == 2, 'There must be two versions of product')
        need(versions[0][2] == old_category and versions[1][2] == NEW_CATEGORY,
             'Expected old and new categories')
        need(len({r[2] for r in links}) == 2, 'Facts must reference BOTH SCD versions')
        need(baseline_january == after_january, 'Historical January revenue changed!')
        need(counts[0] == len(sales) and counts[1] == baseline_total,
             'Count or canonical revenue changed!')
        need(overlaps == 0, 'At least one sale references version outside validity')

        print(f'BEFORE Jan 2024 revenue by category: {baseline_january}')
        print(f'AFTER  Jan 2024 revenue by category: {after_january}')
        print(f'SCD2 product_id={PRODUCT_ID}: {len(versions)} versions; original={old_category}, new={NEW_CATEGORY}')
        print(f'Facts linked to versions: {len(links)}; distinct product_sk: {len({r[2] for r in links})}')
        print(f'fact_sales_scd2 count={counts[0]} total_revenue={counts[1]} validity_errors={overlaps}')
        print('PASS: historical January unchanged; new category version used for February sales')

        dest.close()
        dest = None
        # Publish verified data only. Keep source P03/P05 database unmodified.
        tmp.replace(TARGET)
        tmp = None
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            '# З06 — результаты демонстрации SCD2',
            '', '**Студент:** Лежень А.В. · **Группа:** 233 · **Домен:** D1 — Розница',
            '', f'Учебная смена `dim_product.category` для `product_id = {PRODUCT_ID}` с {BOUNDARY.isoformat()}.',
            f'До: **{old_category}**; после: **{NEW_CATEGORY}**. Изменение **смоделировано**, в исходных CSV его нет.',
            '', '## Две версии товара',
            '', md_table(['product_sk','product_id','category','valid_from','valid_to (exclusive)','is_current'], versions),
            '', '## Связь фактов с версией товара',
            '', md_table(['sale_id','full_date','product_sk','category','amount'], links),
            '', '## Исторический срез: январь 2024 до изменения',
            '', md_table(['category','revenue'], baseline_january),
            '', '## Исторический срез: январь 2024 после изменения',
            '', md_table(['category','revenue'], after_january),
            '', '## Контроль',
            '', f'- Факт: **{counts[0]} строк**; главная метрика: **{counts[1]}**.',
            f'- Некорректных соответствий интервалам версий: **{overlaps}**.',
            '- Январский отчёт до и после изменения **совпадает**.',
            '- `fact_sales_scd2.product_sk` привязан к версии по дате события (as-of JOIN).',
            '- З03–З05 остаются без изменения; демонстрация выполняется в отдельном DuckDB-файле.',
            '', '**Результат:** PASS — исторические продажи не переписаны.',
        ]
        REPORT.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        print(f'OK: demo DB={TARGET}')
        print(f'OK: results={REPORT}')
    finally:
        source.close()
        if dest is not None:
            dest.close()
        if tmp is not None:
            tmp.unlink(missing_ok=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        sys.exit(1)
