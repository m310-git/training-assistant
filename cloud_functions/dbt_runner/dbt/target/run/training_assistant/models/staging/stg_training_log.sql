-- back compat for old kwarg name
  
  
        
            
	    
	    
            
        
    

    

    merge into `training-assistant-prod`.`staging`.`stg_training_log` as DBT_INTERNAL_DEST
        using (
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
        ) as DBT_INTERNAL_SOURCE
        on ((DBT_INTERNAL_SOURCE.log_id = DBT_INTERNAL_DEST.log_id))

    
    when matched then update set
        `log_id` = DBT_INTERNAL_SOURCE.`log_id`,`user_id` = DBT_INTERNAL_SOURCE.`user_id`,`exercise_name` = DBT_INTERNAL_SOURCE.`exercise_name`,`body_part` = DBT_INTERNAL_SOURCE.`body_part`,`training_date` = DBT_INTERNAL_SOURCE.`training_date`,`set_number` = DBT_INTERNAL_SOURCE.`set_number`,`weight_kg` = DBT_INTERNAL_SOURCE.`weight_kg`,`reps` = DBT_INTERNAL_SOURCE.`reps`,`volume` = DBT_INTERNAL_SOURCE.`volume`,`rpe` = DBT_INTERNAL_SOURCE.`rpe`,`memo` = DBT_INTERNAL_SOURCE.`memo`,`created_at` = DBT_INTERNAL_SOURCE.`created_at`,`updated_at` = DBT_INTERNAL_SOURCE.`updated_at`
    

    when not matched then insert
        (`log_id`, `user_id`, `exercise_name`, `body_part`, `training_date`, `set_number`, `weight_kg`, `reps`, `volume`, `rpe`, `memo`, `created_at`, `updated_at`)
    values
        (`log_id`, `user_id`, `exercise_name`, `body_part`, `training_date`, `set_number`, `weight_kg`, `reps`, `volume`, `rpe`, `memo`, `created_at`, `updated_at`)


    