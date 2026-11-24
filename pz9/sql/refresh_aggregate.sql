-- Execute after EVERY successful Z07 fact reload. This is a full rebuild, not an incremental MV.
-- Grain: one row = one calendar day + one store.
TRUNCATE TABLE retail_pz7.agg_daily_store_sales;

INSERT INTO retail_pz7.agg_daily_store_sales
    (sale_date, store_id, amount_sum, qty_sum, sales_rows)
SELECT
    d.full_date AS sale_date,
    f.store_id AS store_id,
    sum(f.amount) AS amount_sum,
    sum(toInt64(f.qty)) AS qty_sum,
    count() AS sales_rows
FROM retail_pz7.fact_sales AS f
INNER JOIN retail_pz7.dim_date AS d ON f.date_id = d.date_id
GROUP BY d.full_date, f.store_id;
