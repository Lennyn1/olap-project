-- Z10 / Native SQL / bar chart «Выручка по категориям»
-- date_filter: Field Filter -> retail_pz7.dim_date.full_date, alias d.
SELECT p.category AS category, SUM(f.amount) AS total_revenue
FROM retail_pz7.fact_sales AS f
INNER JOIN retail_pz7.dim_product AS p ON f.product_id = p.product_id
INNER JOIN retail_pz7.dim_date AS d ON f.date_id = d.date_id
[[WHERE {{date_filter}}]]
GROUP BY p.category
ORDER BY total_revenue DESC, category
