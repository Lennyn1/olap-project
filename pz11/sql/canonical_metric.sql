-- Z11 / canonical metric. Source of truth: detailed fact, no BI filter.
SELECT SUM(amount) AS total_revenue
FROM retail_pz7.fact_sales;
