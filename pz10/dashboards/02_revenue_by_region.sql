-- Z10 / Native SQL / bar chart «Выручка по регионам»
-- date_filter: Field Filter -> retail_pz7.dim_date.full_date, alias d.
SELECT s.region AS region, SUM(f.amount) AS total_revenue
FROM retail_pz7.fact_sales AS f
INNER JOIN retail_pz7.dim_store AS s ON f.store_id = s.store_id
INNER JOIN retail_pz7.dim_date AS d ON f.date_id = d.date_id
[[WHERE {{date_filter}}]]
GROUP BY s.region
ORDER BY total_revenue DESC, region
