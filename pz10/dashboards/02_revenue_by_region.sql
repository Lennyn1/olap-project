-- З10. Выручка по регионам (Native SQL, Metabase)
-- Metabase variable: period -> Field Filter -> dim_date.full_date
SELECT
    s.region AS region,
    SUM(f.amount) AS total_revenue
FROM retail_pz7.fact_sales AS f
JOIN retail_pz7.dim_store AS s
    ON f.store_id = s.store_id
JOIN retail_pz7.dim_date
    ON f.date_id = dim_date.date_id
WHERE 1 = 1
[[AND {{period}}]]
GROUP BY s.region
ORDER BY total_revenue DESC;
