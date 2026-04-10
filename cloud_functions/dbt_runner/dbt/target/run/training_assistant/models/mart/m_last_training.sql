
  
    

    create or replace table `training-assistant-prod`.`mart`.`m_last_training`
      
    
    

    OPTIONS()
    as (
      

WITH last_per_body_part AS (
    SELECT
        user_id,
        body_part_id,
        body_part_name,
        MAX(training_date) AS last_training_date
    FROM `training-assistant-prod`.`mart`.`fct_training_set`
    GROUP BY 1, 2, 3
),

last_overall AS (
    SELECT
        user_id,
        MAX(training_date) AS last_training_date_any
    FROM `training-assistant-prod`.`mart`.`fct_training_set`
    GROUP BY 1
)

SELECT
    bp.user_id,
    bp.body_part_id,
    bp.body_part_name,
    bp.last_training_date,
    DATE_DIFF(CURRENT_DATE('Asia/Tokyo'), bp.last_training_date, DAY)
        AS days_since_last_bodypart,
    DATE_DIFF(CURRENT_DATE('Asia/Tokyo'), o.last_training_date_any, DAY)
        AS days_since_last_any,
    DATE_DIFF(CURRENT_DATE('Asia/Tokyo'), o.last_training_date_any, DAY) >= 3
        AS needs_3day_reminder,
    CASE
        WHEN bp.body_part_id = 'other' THEN FALSE
        ELSE DATE_DIFF(CURRENT_DATE('Asia/Tokyo'), bp.last_training_date, DAY) >= 7
    END AS needs_7day_reminder
FROM last_per_body_part bp
LEFT JOIN last_overall o
    ON bp.user_id = o.user_id
    );
  