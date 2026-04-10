
    
    

with dbt_test__target as (

  select body_part_id as unique_field
  from `training-assistant-prod`.`mart`.`d_body_part`
  where body_part_id is not null

)

select
    unique_field,
    count(*) as n_records

from dbt_test__target
group by unique_field
having count(*) > 1


