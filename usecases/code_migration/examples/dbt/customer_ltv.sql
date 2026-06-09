{{ config(materialized='table') }}

-- Per-customer lifetime value over completed orders.
-- ref()/source() resolve to the shared input tables (customers, orders).
SELECT
    c.customer_id,
    ROUND(SUM(o.amount), 2) AS lifetime_value,
    COUNT(*)                AS num_orders
FROM {{ ref('customers') }} c
JOIN {{ source('raw', 'orders') }} o
    ON o.customer_id = c.customer_id
WHERE o.status = 'completed'
GROUP BY c.customer_id
ORDER BY lifetime_value DESC, c.customer_id
