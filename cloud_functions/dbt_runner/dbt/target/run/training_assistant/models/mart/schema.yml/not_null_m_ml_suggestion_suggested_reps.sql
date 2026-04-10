
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select suggested_reps
from `training-assistant-prod`.`staging`.`m_ml_suggestion`
where suggested_reps is null



  
  
      
    ) dbt_internal_test