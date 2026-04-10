
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select exercise_id
from `training-assistant-prod`.`mart`.`d_exercise`
where exercise_id is null



  
  
      
    ) dbt_internal_test