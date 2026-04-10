

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
