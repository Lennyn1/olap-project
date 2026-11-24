-- Z06 / P06: isolated educational SCD2 demonstration in DuckDB
-- Student: Лежень А.В., group 233; D1 Retail
-- validity intervals: [valid_from, valid_to), NULL valid_to = current/no upper bound
CREATE TABLE dim_product_scd2 (
    product_sk BIGINT PRIMARY KEY,
    product_id INTEGER NOT NULL,
    product_name VARCHAR NOT NULL,
    category VARCHAR NOT NULL,
    brand VARCHAR NOT NULL,
    valid_from DATE NOT NULL,
    valid_to DATE,
    is_current BOOLEAN NOT NULL,
    CHECK (valid_to IS NULL OR valid_to > valid_from)
);

CREATE TABLE fact_sales_scd2 (
    sale_id BIGINT PRIMARY KEY,
    date_id INTEGER NOT NULL,
    store_id INTEGER NOT NULL,
    product_sk BIGINT NOT NULL REFERENCES dim_product_scd2(product_sk),
    qty INTEGER NOT NULL,
    amount DECIMAL(12, 2) NOT NULL
);
