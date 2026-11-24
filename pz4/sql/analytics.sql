-- З04 / P04 | Лежень А.В., группа 233 | D1: Розница
-- DuckDB database: pz3/retail_local.duckdb
-- Grain: одна строка fact_sales = одна позиция продажи товара в магазине за дату.

-- Q1 / Slice / Вопрос паспорта 1: выручка по регионам за январь 2024 года.
SELECT s.region, SUM(f.amount) AS total_revenue
FROM fact_sales AS f
JOIN dim_store AS s ON f.store_id = s.store_id
JOIN dim_date AS d ON f.date_id = d.date_id
WHERE d.year = 2024 AND d.month = 1
GROUP BY s.region
ORDER BY total_revenue DESC, s.region;

-- Q2 / Roll-up / Вопрос паспорта 3: динамика выручки по месяцам 2024 года
-- Уровень месяца:
SELECT d.year, d.month, SUM(f.amount) AS total_revenue
FROM fact_sales AS f
JOIN dim_date AS d ON f.date_id = d.date_id
WHERE d.year = 2024
GROUP BY d.year, d.month
ORDER BY d.year, d.month;

-- Q2b / Roll-up / Та же мера на уровне года:
SELECT d.year, SUM(f.amount) AS total_revenue
FROM fact_sales AS f
JOIN dim_date AS d ON f.date_id = d.date_id
GROUP BY d.year
ORDER BY d.year;

-- Q3 / Dice / Вопрос паспорта 2: какие категории дают наибольшую выручку?
-- Разрез: регион + категория; JOIN двух измерений и сортировка по выручке.
SELECT s.region, p.category, SUM(f.amount) AS total_revenue
FROM fact_sales AS f
JOIN dim_store AS s ON f.store_id = s.store_id
JOIN dim_product AS p ON f.product_id = p.product_id
GROUP BY s.region, p.category
ORDER BY total_revenue DESC, s.region, p.category;

-- Q4 / Window / Дополнение к вопросу 2: доля и место категории по выручке.
WITH category_revenue AS (
    SELECT p.category, SUM(f.amount) AS total_revenue
    FROM fact_sales AS f
    JOIN dim_product AS p ON f.product_id = p.product_id
    GROUP BY p.category
)
SELECT category,
       total_revenue,
       ROUND(100.0 * total_revenue / NULLIF(SUM(total_revenue) OVER (), 0), 2) AS revenue_share_pct,
       RANK() OVER (ORDER BY total_revenue DESC) AS revenue_rank
FROM category_revenue
ORDER BY revenue_rank, category;

-- Q5 / Top-N / Дополнительно: пять магазинов с наибольшей выручкой.
SELECT s.store_id, s.store_name, s.region, SUM(f.amount) AS total_revenue
FROM fact_sales AS f
JOIN dim_store AS s ON f.store_id = s.store_id
GROUP BY s.store_id, s.store_name, s.region
ORDER BY total_revenue DESC, s.store_id
LIMIT 5;
