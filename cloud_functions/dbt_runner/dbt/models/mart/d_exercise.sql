{{
    config(materialized='table', schema='mart')
}}

SELECT
    exercise_id,
    exercise_name,
    body_part_id,
    is_compound,
    is_active,
    display_order,
    updated_at
FROM {{ source('raw', 'exercise_master') }}
WHERE is_active = TRUE