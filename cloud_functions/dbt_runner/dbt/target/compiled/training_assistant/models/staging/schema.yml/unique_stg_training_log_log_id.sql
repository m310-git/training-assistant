
    
    

with dbt_test__target as (

  select log_id as unique_field
  from `training-assistant-prod`.`staging`.`stg_training_log`
  where log_id is not null

)

select
    unique_field,
    count(*) as n_records

from dbt_test__target
group by unique_field
having count(*) > 1


