{{
    config(materialized='table', schema='mart')
}}

WITH alltime_volume AS (
    SELECT
        f.user_id,
        u.user_name,
        SUM(f.volume) AS total_volume
    FROM {{ ref('fct_training_set') }} f
    LEFT JOIN {{ ref('d_user') }} u ON f.user_id = u.user_id
    GROUP BY 1, 2
)

SELECT
    *,
    RANK() OVER (ORDER BY total_volume DESC) AS rank
FROM alltime_volume