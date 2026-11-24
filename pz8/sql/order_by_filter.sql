-- Experiment with leading ORDER BY column (date_id).
SELECT count() AS rows_for_date, SUM(amount) AS revenue_for_date
FROM retail_pz7.fact_sales
WHERE date_id = 20240101;

-- Optional inspection of the primary index usage (small sample, not a benchmark):
EXPLAIN indexes = 1 SELECT count() FROM retail_pz7.fact_sales WHERE date_id = 20240101;
