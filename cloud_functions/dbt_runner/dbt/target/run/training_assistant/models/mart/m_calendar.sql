
  
    

    create or replace table `training-assistant-prod`.`mart`.`m_calendar`
      
    
    

    OPTIONS()
    as (
      

WITH daily_exercises AS (
    SELECT
        user_id,
        training_date,
        body_part_name,
        exercise_name,
        MAX(weight_kg) AS max_weight
    FROM `training-assistant-prod`.`mart`.`fct_training_set`
    GROUP BY 1, 2, 3, 4
),

exercise_labels AS (
    SELECT
        user_id,
        training_date,
        STRING_AGG(
            CONCAT(exercise_name, ': ', CAST(max_weight AS STRING), 'kg'),
            ' / '
        ) AS exercise_summary
    FROM daily_exercises
    GROUP BY 1, 2
),

daily_body_parts AS (
    SELECT
        user_id,
        training_date,
        STRING_AGG(DISTINCT body_part_name, ', ') AS body_parts
    FROM daily_exercises
    GROUP BY 1, 2
),

daily_totals AS (
    SELECT
        user_id,
        training_date,
        SUM(volume) AS total_volume,
        COUNT(DISTINCT exercise_id) AS exercise_count
    FROM `training-assistant-prod`.`mart`.`fct_training_set`
    GROUP BY 1, 2
)

SELECT
    t.user_id,
    t.training_date,
    bp.body_parts,
    t.total_volume,
    t.exercise_count,
    el.exercise_summary
FROM daily_totals t
LEFT JOIN daily_body_parts bp
    ON t.user_id = bp.user_id AND t.training_date = bp.training_date
LEFT JOIN exercise_labels el
    ON t.user_id = el.user_id AND t.training_date = el.training_date
    );
  