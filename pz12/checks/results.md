# З12 — проверка зачётного контура

**Лежень А.В. · группа 233 · D1 Розница**

**Дата UTC:** 2026-11-24T04:49:44+00:00
**Режим:** только чтение, без пересоздания БД

| Проверка | Статус | Данные |
|---|---|---|
| raw dim_date | PASS | 8 rows |
| raw dim_store | PASS | 5 rows |
| raw dim_product | PASS | 8 rows |
| raw fact_sales | PASS | 15 rows |
| DuckDB | PASS | fact_sales=15, SUM(amount)=264.00 |
| CH dim_date | PASS | 8 rows |
| CH dim_store | PASS | 5 rows |
| CH dim_product | PASS | 8 rows |
| CH fact_sales | PASS | 15 rows |
| CH canonical | PASS | SUM(amount)=264.00 |
| CH duplicate sale_id | PASS | 0 |
| CH fact MergeTree/order | PASS | engine=MergeTree, sorting_key=date_id, store_id, product_id |
| CH aggregate | PASS | groups=13, covered_sales=15, SUM(amount_sum)=264.00 |
| CH January fact vs aggregate | PASS | fact=125.50, aggregate=125.50 |
| file pz2/passport.md | PASS | present |
| file pz2/cut.md | PASS | present |
| file pz7/sql/ddl_clickhouse.sql | PASS | present |
| file pz10/dashboards/01_total_revenue.sql | PASS | present |
| file pz11/checks/results.md | PASS | present |

**Итог автоматических проверок:** PASS

**Metabase:** не проверяется скриптом. Нужна отдельная ручная проверка дашборда, SQL Native, общего фильтра и протокола З11.
