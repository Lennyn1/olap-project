-- Z09: canonical metric always comes from detailed fact_sales.
SELECT count() AS fact_rows, sum(amount) AS fact_revenue
FROM retail_pz7.fact_sales;

SELECT count() AS aggregate_rows,
       sum(sales_rows) AS covered_fact_rows,
       sum(amount_sum) AS aggregate_revenue
FROM retail_pz7.agg_daily_store_sales;

-- Check all day x store groups: expected 0 rows.
SELECT
    d.full_date AS sale_date,
    f.store_id AS store_id,
    sum(f.amount) AS fact_amount,
    a.amount_sum AS agg_amount
FROM retail_pz7.fact_sales f
INNER JOIN retail_pz7.dim_date d ON f.date_id = d.date_id
LEFT JOIN retail_pz7.agg_daily_store_sales a
    ON a.sale_date = d.full_date AND a.store_id = f.store_id
GROUP BY d.full_date, f.store_id, a.amount_sum
HAVING a.amount_sum IS NULL OR fact_amount != a.amount_sum;
