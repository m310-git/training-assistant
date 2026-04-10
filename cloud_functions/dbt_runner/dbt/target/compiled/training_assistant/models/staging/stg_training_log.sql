
WITH source AS (
    SELECT * FROM `training-assistant-prod`.`raw`.`training_log`
    WHERE is_deleted = FALSE
    
    AND updated_at > (SELECT MAX(updated_at) FROM `training-assistant-prod`.`staging`.`stg_training_log`)
    
),
deduplicated AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY log_id
            ORDER BY updated_at DESC
        ) AS row_num
    FROM source
),
cleaned AS (
    SELECT
        log_id,
        user_id,
        LOWER(TRIM(exercise_name))  AS exercise_name,
        LOWER(TRIM(body_part))      AS body_part,
        training_date,
        set_number,
        ROUND(weight_kg, 1)         AS weight_kg,
        reps,
        ROUND(weight_kg * reps, 1)  AS volume,
        CASE
            WHEN rpe BETWEEN 6.0 AND 10.0 THEN ROUND(rpe, 1)
            ELSE NULL
        END AS rpe,
        memo,
        created_at,
        updated_at
    FROM deduplicated
    WHERE row_num = 1
)
SELECT * FROM cleaned