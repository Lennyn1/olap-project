-- P03 checks: run after loading, using a DuckDB connection.
SHOW TABLES;

SELECT 'dim_date' AS table_name, COUNT(*) AS row_count FROM dim_date
UNION ALL SELECT 'dim_store', COUNT(*) FROM dim_store
UNION ALL SELECT 'dim_product', COUNT(*) FROM dim_product
UNION ALL SELECT 'fact_sales', COUNT(*) FROM fact_sales;

SELECT SUM(amount) AS total_revenue, SUM(qty) AS total_quantity FROM fact_sales;

SELECT COUNT(*) AS null_fact_keys
FROM fact_sales
WHERE sale_id IS NULL OR date_id IS NULL OR store_id IS NULL OR product_id IS NULL;

-- An anti-join checks missing dimension references (orphan keys).
SELECT COUNT(*) AS orphan_dates
FROM fact_sales AS f LEFT JOIN dim_date AS d ON f.date_id = d.date_id
WHERE d.date_id IS NULL;

SELECT COUNT(*) AS orphan_stores
FROM fact_sales AS f LEFT JOIN dim_store AS s ON f.store_id = s.store_id
WHERE s.store_id IS NULL;

SELECT COUNT(*) AS orphan_products
FROM fact_sales AS f LEFT JOIN dim_product AS p ON f.product_id = p.product_id
WHERE p.product_id IS NULL;
