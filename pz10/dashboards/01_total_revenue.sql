-- Z10 / Native SQL / KPI «Общая выручка»
-- Without dashboard filter: same result as canonical SQL on fact_sales (264.00).
-- Metabase variable date_filter: Field Filter, field retail_pz7.dim_date.full_date,
-- table alias d (if Metabase offers a field/table alias setting).
SELECT SUM(f.amount) AS total_revenue
FROM retail_pz7.fact_sales AS f
INNER JOIN retail_pz7.dim_date AS d ON f.date_id = d.date_id
[[WHERE {{date_filter}}]]
