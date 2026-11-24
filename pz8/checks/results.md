# Z08 — ClickHouse vs DuckDB: результаты сверки

**Студент:** Лежень А.В.  
**Группа:** 233  
**Домен:** D1 — Розница  
**Дата UTC:** 2026-11-24T03:36:03+00:00

**Источники:** DuckDB `pz3/retail_local.duckdb` и ClickHouse `retail_pz7` (одинаковая витрина).

## canonical metric — MATCH

| total_revenue |
| --- |
| 264.00 |

## Q1 slice — MATCH

| region | total_revenue |
| --- | --- |
| Центр | 73.00 |
| Запад | 52.50 |

## Q2 monthly roll-up — MATCH

| year | month | total_revenue |
| --- | --- | --- |
| 2024 | 1 | 125.50 |
| 2024 | 2 | 78.50 |
| 2024 | 3 | 60.00 |

## Q2b yearly roll-up — MATCH

| year | total_revenue |
| --- | --- |
| 2024 | 264.00 |

## Q3 dice — MATCH

| region | category | total_revenue |
| --- | --- | --- |
| Запад | Молочка | 79.50 |
| Центр | Напитки | 61.00 |
| Запад | Напитки | 50.00 |
| Центр | Молочка | 49.50 |
| Запад | Хлеб | 18.00 |
| Запад | Бакалея | 6.00 |

## Q4 window — MATCH

| category | total_revenue | revenue_share_pct | revenue_rank |
| --- | --- | --- | --- |
| Молочка | 129.00 | 48.86 | 1 |
| Напитки | 111.00 | 42.05 | 2 |
| Хлеб | 18.00 | 6.82 | 3 |
| Бакалея | 6.00 | 2.27 | 4 |

## Q5 top-N — MATCH

| store_id | store_name | region | total_revenue |
| --- | --- | --- | --- |
| 2 | Корона | Запад | 77.00 |
| 3 | Немига | Центр | 68.50 |
| 1 | Центр | Запад | 49.00 |
| 4 | Галерея | Центр | 42.00 |
| 5 | Брест-Парк | Запад | 27.50 |

## ORDER BY: фильтр по ведущему полю

`fact_sales` хранится в ClickHouse с `ORDER BY (date_id, store_id, product_id)`. Эксперимент фильтрует по `date_id = 20240101`.

| Система | Строк за дату | Выручка за дату |
| --- | --- | --- |
| DuckDB | 2 | 32.50 |
| ClickHouse | 2 | 32.5 |

### EXPLAIN indexes = 1 (ClickHouse)

```text
Expression ((Project names + Projection))
  Aggregating
    Expression (Before GROUP BY)
      Filter ((WHERE + Change column names to column identifiers))
        ReadFromMergeTree (retail_pz7.fact_sales)
        Indexes:
          PrimaryKey
            Keys: 
              date_id
            Condition: (date_id in [20240101, 20240101])
            Parts: 1/1
            Granules: 1/1
```

## Вывод

Все шесть запросов из З04 и эталон `SUM(amount)` вернули одинаковые данные в DuckDB и ClickHouse. Эталон на sample равен **264.00**. Фильтр по ведущему полю `date_id` также даёт одинаковый результат. `ORDER BY` задаёт порядок хранения и индекс разреженного типа, **но не обеспечивает уникальность**. На 15 строках ускорение не измеряем. Месячное `PARTITION BY` сознательно не используется: слишком мелкие партиции не дают пользы на sample; решение и цена отказа описаны в `notes/partition_decision.md` и добавлении в `pz2/cut.md`.
