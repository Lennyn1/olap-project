-- З10. Общая выручка (Native SQL, Metabase)
-- Канон без фильтра: SUM(amount) FROM retail_pz7.fact_sales = 264.00
-- Metabase variable: period -> Field Filter -> dim_date.full_date
SELECT SUM(f.amount) AS total_revenue
FROM retail_pz7.fact_sales AS f
JOIN retail_pz7.dim_date
    ON f.date_id = dim_date.date_id
WHERE 1 = 1
[[AND {{period}}]];
