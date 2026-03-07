{{
    config(materialized='table', schema='mart')
}}

WITH monthly_volume AS (
    SELECT
        f.user_id,
        u.user_name,
        DATE_TRUNC(f.training_date, MONTH) AS month,
        SUM(f.volume) AS total_volume
    FROM {{ ref('fct_training_set') }} f
    LEFT JOIN {{ ref('d_user') }} u ON f.user_id = u.user_id
    GROUP BY 1, 2, 3
),

ranked AS (
    SELECT
        *,
        RANK() OVER (
            PARTITION BY month
            ORDER BY total_volume DESC
        ) AS rank
    FROM monthly_volume
),

with_prev AS (
    SELECT
        r.*,
        LAG(r.rank) OVER (
            PARTITION BY r.user_id
            ORDER BY r.month
        ) AS prev_rank,
        LAG(r.total_volume) OVER (
            PARTITION BY r.user_id
            ORDER BY r.month
        ) AS prev_volume
    FROM ranked r
)

SELECT
    *,
    CASE
        WHEN prev_rank IS NULL THEN 'NEW'
        WHEN rank < prev_rank THEN 'UP'
        WHEN rank > prev_rank THEN 'DOWN'
        ELSE 'SAME'
    END AS rank_change,
    CASE
        WHEN prev_rank IS NULL THEN NULL
        ELSE prev_rank - rank
    END AS rank_diff
FROM with_prev