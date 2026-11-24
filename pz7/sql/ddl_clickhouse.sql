-- Z07 / P07, D1 retail. Student: Лежень А.В., group 233.
-- Dedicated project database (does not modify course database retail_dw).
-- Run via pz7/etl/load_clickhouse.py; it executes these statements one by one.
CREATE DATABASE IF NOT EXISTS retail_pz7;

CREATE TABLE retail_pz7.dim_date
(
    date_id UInt32,
    full_date Date,
    year UInt16,
    month UInt8,
    month_name String,
    day_of_week UInt8
)
ENGINE = MergeTree
ORDER BY date_id;

CREATE TABLE retail_pz7.dim_store
(
    store_id UInt32,
    store_name String,
    city String,
    region String
)
ENGINE = MergeTree
ORDER BY store_id;

CREATE TABLE retail_pz7.dim_product
(
    product_id UInt32,
    product_name String,
    category String,
    brand String
)
ENGINE = MergeTree
ORDER BY product_id;

CREATE TABLE retail_pz7.fact_sales
(
    sale_id UInt64,
    date_id UInt32,
    store_id UInt32,
    product_id UInt32,
    qty Int32,
    amount Decimal(12, 2)
)
ENGINE = MergeTree
ORDER BY (date_id, store_id, product_id);
