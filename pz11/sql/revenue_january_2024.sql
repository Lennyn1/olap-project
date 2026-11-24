-- Z11 / same SUM(amount), dashboard period: 2024-01-01 .. 2024-01-31 inclusive.
-- Mirrors Metabase Field Filter on dim_date.full_date.
SELECT SUM(f.amount) AS total_revenue
FROM retail_pz7.fact_sales AS f
JOIN retail_pz7.dim_date AS d ON f.date_id = d.date_id
WHERE d.full_date >= toDate('2024-01-01')
  AND d.full_date < toDate('2024-02-01');
