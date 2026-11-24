-- З03 / P03: DuckDB star schema, D1 retail
-- Student: Лежень А.В., group 233
-- Grain: one recorded sale position for a product, store, and calendar date.

CREATE TABLE IF NOT EXISTS dim_date (
    date_id INTEGER PRIMARY KEY,
    full_date DATE NOT NULL,
    year SMALLINT NOT NULL,
    month TINYINT NOT NULL,
    month_name VARCHAR NOT NULL,
    day_of_week TINYINT NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_store (
    store_id INTEGER PRIMARY KEY,
    store_name VARCHAR NOT NULL,
    city VARCHAR NOT NULL,
    region VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_product (
    product_id INTEGER PRIMARY KEY,
    product_name VARCHAR NOT NULL,
    category VARCHAR NOT NULL,
    brand VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS fact_sales (
    sale_id BIGINT PRIMARY KEY,
    date_id INTEGER NOT NULL REFERENCES dim_date(date_id),
    store_id INTEGER NOT NULL REFERENCES dim_store(store_id),
    product_id INTEGER NOT NULL REFERENCES dim_product(product_id),
    qty INTEGER NOT NULL,
    amount DECIMAL(12, 2) NOT NULL
);
