{{
    config(materialized='table', schema='mart')
}}

SELECT
    user_id,
    user_name,
    line_user_id,
    is_active,
    created_at
FROM {{ source('raw', 'user_master') }}
WHERE is_active = TRUE
