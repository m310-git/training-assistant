{{
    config(materialized='table', schema='mart')
}}

WITH max_weight AS (
    SELECT
        user_id,
        exercise_id,
        exercise_name,
        'max_weight' AS record_type,
        MAX(weight_kg) AS record_value,
        ARRAY_AGG(training_date ORDER BY weight_kg DESC, training_date DESC LIMIT 1)[OFFSET(0)] AS achieved_date
    FROM {{ ref('fct_training_set') }}
    GROUP BY 1, 2, 3
),

max_volume AS (
    SELECT
        user_id,
        exercise_id,
        exercise_name,
        'max_volume' AS record_type,
        MAX(volume) AS record_value,
        ARRAY_AGG(training_date ORDER BY volume DESC, training_date DESC LIMIT 1)[OFFSET(0)] AS achieved_date
    FROM {{ ref('fct_training_set') }}
    GROUP BY 1, 2, 3
),

combined AS (
    SELECT * FROM max_weight
    UNION ALL
    SELECT * FROM max_volume
),

with_previous AS (
    SELECT
        c.*,
        u.user_name,
        (
            SELECT MAX(
                CASE
                    WHEN c.record_type = 'max_weight' THEN f.weight_kg
                    ELSE f.volume
                END
            )
            FROM {{ ref('fct_training_set') }} f
            WHERE f.user_id = c.user_id
              AND f.exercise_id = c.exercise_id
              AND f.training_date < c.achieved_date
        ) AS previous_value,
        DATE_DIFF(CURRENT_DATE('Asia/Tokyo'), c.achieved_date, DAY) <= 7 AS is_new
    FROM combined c
    LEFT JOIN {{ ref('d_user') }} u ON c.user_id = u.user_id
)

SELECT
    user_id,
    user_name,
    exercise_id,
    exercise_name,
    record_type,
    record_value,
    achieved_date,
    previous_value,
    is_new
FROM with_previous