{{
    config(
        materialized='incremental', schema='mart',
        unique_key='log_id',
        partition_by={
            "field": "training_date",
            "data_type": "date",
            "granularity": "month"
        }
    )
}}

SELECT
    s.log_id,
    s.user_id,
    s.training_date,
    e.exercise_id,
    e.exercise_name,
    e.is_compound,
    bp.body_part_id,
    bp.body_part_name,
    s.set_number,
    s.weight_kg,
    s.reps,
    s.volume,
    s.rpe,
    s.memo,
    s.created_at
FROM {{ ref('stg_training_log') }} s
LEFT JOIN {{ ref('d_exercise') }} e
    ON LOWER(TRIM(s.exercise_name)) = LOWER(TRIM(e.exercise_name))
LEFT JOIN {{ ref('d_body_part') }} bp
    ON LOWER(TRIM(s.body_part)) = bp.body_part_id

{% if is_incremental() %}
WHERE s.updated_at > (SELECT MAX(created_at) FROM {{ this }})
{% endif %}