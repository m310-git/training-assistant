
    
    

with dbt_test__target as (

  select exercise_id as unique_field
  from `training-assistant-prod`.`mart`.`d_exercise`
  where exercise_id is not null

)

select
    unique_field,
    count(*) as n_records

from dbt_test__target
group by unique_field
having count(*) > 1


