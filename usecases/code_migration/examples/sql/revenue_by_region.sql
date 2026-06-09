-- Total completed-order revenue per region.
-- Inputs: orders, customers, regions (registered as temp views by the harness).
SELECT
    r.region_name,
    ROUND(SUM(o.amount), 2) AS total_revenue,
    COUNT(*)                AS order_count
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
JOIN regions   r ON c.region_id  = r.region_id
WHERE o.status = 'completed'
GROUP BY r.region_name
ORDER BY total_revenue DESC, r.region_name
