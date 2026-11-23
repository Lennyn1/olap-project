# Star Schema — D1 «Розница»

```mermaid
erDiagram
    dim_date ||--o{ fact_sales : "date_id"
    dim_store ||--o{ fact_sales : "store_id"
    dim_product ||--o{ fact_sales : "product_id"

    fact_sales {
        UInt64 sale_id PK
        UInt32 date_id FK
        UInt32 store_id FK
        UInt32 product_id FK
        Int32 qty
        Decimal amount
    }
    dim_date {
        UInt32 date_id PK
        Date full_date
        UInt16 year
        UInt8 month
        String month_name
        UInt8 day_of_week
    }
    dim_store {
        UInt32 store_id PK
        String store_name
        String city
        String region
    }
    dim_product {
        UInt32 product_id PK
        String product_name
        String category
        String brand
    }
```

**Зерно:** одна строка `fact_sales` — одна позиция продажи товара в конкретном магазине на конкретную дату (`sale_id` — идентификатор строки, не номер чека).

**Главная метрика:** `SUM(fact_sales.amount)` — общая выручка.

**Примечание:** `PK`/`FK` на схеме — логические ключи аналитической модели. Исходный ClickHouse DDL задаёт `MergeTree ORDER BY`, не SQL-ограничения первичного/внешнего ключа. Схема соответствует четырём таблицам `init/01_schema.sql` учебного стенда.
