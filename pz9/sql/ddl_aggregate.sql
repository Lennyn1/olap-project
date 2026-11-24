-- Z09: day x store aggregate for the future Metabase revenue line chart.
-- Source of truth remains retail_pz7.fact_sales.
CREATE TABLE IF NOT EXISTS retail_pz7.agg_daily_store_sales
(
    sale_date Date,
    store_id UInt32,
    amount_sum Decimal(18, 2),
    qty_sum Int64,
    sales_rows UInt64
)
ENGINE = MergeTree
ORDER BY (sale_date, store_id);
