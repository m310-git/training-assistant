
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select log_id
from `training-assistant-prod`.`staging`.`stg_training_log`
where log_id is null



  
  
      
    ) dbt_internal_test