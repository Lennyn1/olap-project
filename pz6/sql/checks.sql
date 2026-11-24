-- SHOW 2 VERSIONS (for the demo product)
SELECT product_sk, product_id, product_name, category, valid_from, valid_to, is_current
FROM dim_product_scd2
WHERE product_id = 101
ORDER BY valid_from;

-- Link between fact, chosen version, and original sale date (source dim_date)
-- This script is run by run_scd2.py with a temporary source_dates table.
SELECT f.sale_id, d.full_date, p.product_id, p.product_sk, p.category, f.amount
FROM fact_sales_scd2 f
JOIN dim_product_scd2 p ON f.product_sk = p.product_sk
JOIN source_dates d ON f.date_id = d.date_id
WHERE p.product_id = 101
ORDER BY d.full_date, f.sale_id;

-- Historical report for January 2024, attributed to category valid on sale date
SELECT p.category, SUM(f.amount) AS revenue
FROM fact_sales_scd2 f
JOIN dim_product_scd2 p ON f.product_sk = p.product_sk
JOIN source_dates d ON d.date_id = f.date_id
WHERE d.full_date >= DATE '2024-01-01' AND d.full_date < DATE '2024-02-01'
GROUP BY p.category
ORDER BY p.category;
