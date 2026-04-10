
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select volume
from `training-assistant-prod`.`staging`.`stg_training_log`
where volume is null



  
  
      
    ) dbt_internal_test