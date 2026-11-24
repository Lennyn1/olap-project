-- З04: эталон метрики D1, DuckDB (pz3/retail_local.duckdb)
SELECT SUM(amount) AS total_revenue
FROM fact_sales;
