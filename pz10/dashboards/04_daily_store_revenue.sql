-- Z10 / Native SQL / line chart «Выручка по дням и магазинам»
-- Source is Z09 aggregate; join date for identical date-filter mapping.
-- date_filter: Field Filter -> retail_pz7.dim_date.full_date, alias d.
SELECT a.sale_date AS sale_date,
       s.store_name AS store_name,
       SUM(a.amount_sum) AS total_revenue
FROM retail_pz7.agg_daily_store_sales AS a
INNER JOIN retail_pz7.dim_store AS s ON a.store_id = s.store_id
INNER JOIN retail_pz7.dim_date AS d ON a.sale_date = d.full_date
[[WHERE {{date_filter}}]]
GROUP BY a.sale_date, s.store_name
ORDER BY sale_date, store_name
