-- back compat for old kwarg name
  
  
        
            
	    
	    
            
        
    

    

    merge into `training-assistant-prod`.`mart`.`fct_training_set` as DBT_INTERNAL_DEST
        using (

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
FROM `training-assistant-prod`.`staging`.`stg_training_log` s
LEFT JOIN `training-assistant-prod`.`mart`.`d_exercise` e
    ON LOWER(TRIM(s.exercise_name)) = LOWER(TRIM(e.exercise_name))
LEFT JOIN `training-assistant-prod`.`mart`.`d_body_part` bp
    ON LOWER(TRIM(s.body_part)) = bp.body_part_id


WHERE s.updated_at > (SELECT MAX(created_at) FROM `training-assistant-prod`.`mart`.`fct_training_set`)

        ) as DBT_INTERNAL_SOURCE
        on ((DBT_INTERNAL_SOURCE.log_id = DBT_INTERNAL_DEST.log_id))

    
    when matched then update set
        `log_id` = DBT_INTERNAL_SOURCE.`log_id`,`user_id` = DBT_INTERNAL_SOURCE.`user_id`,`training_date` = DBT_INTERNAL_SOURCE.`training_date`,`exercise_id` = DBT_INTERNAL_SOURCE.`exercise_id`,`exercise_name` = DBT_INTERNAL_SOURCE.`exercise_name`,`is_compound` = DBT_INTERNAL_SOURCE.`is_compound`,`body_part_id` = DBT_INTERNAL_SOURCE.`body_part_id`,`body_part_name` = DBT_INTERNAL_SOURCE.`body_part_name`,`set_number` = DBT_INTERNAL_SOURCE.`set_number`,`weight_kg` = DBT_INTERNAL_SOURCE.`weight_kg`,`reps` = DBT_INTERNAL_SOURCE.`reps`,`volume` = DBT_INTERNAL_SOURCE.`volume`,`rpe` = DBT_INTERNAL_SOURCE.`rpe`,`memo` = DBT_INTERNAL_SOURCE.`memo`,`created_at` = DBT_INTERNAL_SOURCE.`created_at`
    

    when not matched then insert
        (`log_id`, `user_id`, `training_date`, `exercise_id`, `exercise_name`, `is_compound`, `body_part_id`, `body_part_name`, `set_number`, `weight_kg`, `reps`, `volume`, `rpe`, `memo`, `created_at`)
    values
        (`log_id`, `user_id`, `training_date`, `exercise_id`, `exercise_name`, `is_compound`, `body_part_id`, `body_part_name`, `set_number`, `weight_kg`, `reps`, `volume`, `rpe`, `memo`, `created_at`)


    