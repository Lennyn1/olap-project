# Z07 — DuckDB ↔ ClickHouse reconciliation

Студент: Лежень А.В. · группа 233 · домен D1 «Розница»

Дата проверки (UTC): 2026-11-24 03:16:19

| Table | DuckDB | ClickHouse | Match |
|---|---:|---:|---|
| `dim_date` | 8 | 8 | YES |
| `dim_store` | 5 | 5 | YES |
| `dim_product` | 8 | 8 | YES |
| `fact_sales` | 15 | 15 | YES |

**Canonical total_revenue (SUM(amount)): DuckDB 264.00; ClickHouse 264.00; MATCH.**

Duplicate sale IDs: 0; orphan FK: {'date': 0, 'store': 0, 'product': 0}

Full refresh: each run recreates only `retail_pz7`. Repeating the command must keep counts and revenue unchanged.
