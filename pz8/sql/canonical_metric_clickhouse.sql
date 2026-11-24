-- ClickHouse equivalent of pz4/sql/canonical_metric.sql
SELECT SUM(amount) AS total_revenue
FROM retail_pz7.fact_sales;
