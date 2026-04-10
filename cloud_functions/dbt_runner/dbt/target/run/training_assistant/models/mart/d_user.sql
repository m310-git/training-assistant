
  
    

    create or replace table `training-assistant-prod`.`mart`.`d_user`
      
    
    

    OPTIONS()
    as (
      

SELECT
    user_id,
    user_name,
    line_user_id,
    is_active,
    created_at
FROM `training-assistant-prod`.`raw`.`user_master`
WHERE is_active = TRUE
    );
  