-- Z10 reference only: immutable canonical KPI on detail fact (no dashboard filters).
SELECT SUM(amount) AS total_revenue
FROM retail_pz7.fact_sales;
