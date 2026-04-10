
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select reps
from `training-assistant-prod`.`staging`.`stg_training_log`
where reps is null



  
  
      
    ) dbt_internal_test