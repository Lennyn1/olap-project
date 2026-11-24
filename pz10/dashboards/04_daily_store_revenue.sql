-- З10. Выручка по дням и магазинам (Native SQL, Metabase)
-- Источник: агрегат З09. Metabase variable: period -> Field Filter
-- Field Filter column: agg_daily_store_sales.sale_date
-- Table and field alias (if needed): a.sale_date
SELECT
    a.sale_date AS sale_date,
    s.store_name AS store_name,
    SUM(a.amount_sum) AS total_revenue
FROM retail_pz7.agg_daily_store_sales AS a
JOIN retail_pz7.dim_store AS s
    ON a.store_id = s.store_id
WHERE 1 = 1
[[AND {{period}}]]
GROUP BY a.sale_date, s.store_name
ORDER BY a.sale_date, s.store_name;
