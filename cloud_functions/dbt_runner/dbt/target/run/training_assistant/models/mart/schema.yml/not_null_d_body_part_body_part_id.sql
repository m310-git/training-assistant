
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select body_part_id
from `training-assistant-prod`.`mart`.`d_body_part`
where body_part_id is null



  
  
      
    ) dbt_internal_test