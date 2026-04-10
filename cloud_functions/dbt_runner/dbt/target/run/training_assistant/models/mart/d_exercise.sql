
  
    

    create or replace table `training-assistant-prod`.`mart`.`d_exercise`
      
    
    

    OPTIONS()
    as (
      

SELECT
    exercise_id,
    exercise_name,
    body_part_id,
    is_compound,
    is_active,
    display_order,
    updated_at
FROM `training-assistant-prod`.`raw`.`exercise_master`
WHERE is_active = TRUE
    );
  