
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select model_version
from `training-assistant-prod`.`staging`.`m_ml_suggestion`
where model_version is null



  
  
      
    ) dbt_internal_test