
  
    

    create or replace table `training-assistant-prod`.`mart`.`m_progress_curve`
      
    
    

    OPTIONS()
    as (
      

WITH daily AS (
    SELECT
        user_id,
        exercise_id,
        exercise_name,
        is_compound,
        training_date AS metric_date,
        SUM(volume) AS daily_volume,
        COUNT(*) AS total_sets,
        MAX(weight_kg) AS max_weight
    FROM `training-assistant-prod`.`mart`.`fct_training_set`
    GROUP BY 1, 2, 3, 4, 5
),

with_ma AS (
    SELECT
        *,
        AVG(daily_volume) OVER (
            PARTITION BY user_id, exercise_id
            ORDER BY metric_date
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ) AS volume_7d_ma
    FROM daily
),

with_wow AS (
    SELECT
        *,
        ROUND(
            SAFE_DIVIDE(
                volume_7d_ma - LAG(volume_7d_ma, 7) OVER (
                    PARTITION BY user_id, exercise_id
                    ORDER BY metric_date
                ),
                LAG(volume_7d_ma, 7) OVER (
                    PARTITION BY user_id, exercise_id
                    ORDER BY metric_date
                )
            ) * 100,
            2
        ) AS wow_change_pct
    FROM with_ma
)

SELECT * FROM with_wow
    );
  