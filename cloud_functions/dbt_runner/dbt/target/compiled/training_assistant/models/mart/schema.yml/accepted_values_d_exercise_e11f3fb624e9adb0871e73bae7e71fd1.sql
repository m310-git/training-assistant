
    
    

with all_values as (

    select
        body_part_id as value_field,
        count(*) as n_records

    from `training-assistant-prod`.`mart`.`d_exercise`
    group by body_part_id

)

select *
from all_values
where value_field not in (
    'chest','back','shoulder','leg','arm','other'
)


