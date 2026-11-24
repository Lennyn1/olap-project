-- З10. Выручка по категориям (Native SQL, Metabase)
-- Metabase variable: period -> Field Filter -> dim_date.full_date
SELECT
    p.category AS category,
    SUM(f.amount) AS total_revenue
FROM retail_pz7.fact_sales AS f
JOIN retail_pz7.dim_product AS p
    ON f.product_id = p.product_id
JOIN retail_pz7.dim_date
    ON f.date_id = dim_date.date_id
WHERE 1 = 1
[[AND {{period}}]]
GROUP BY p.category
ORDER BY total_revenue DESC;
