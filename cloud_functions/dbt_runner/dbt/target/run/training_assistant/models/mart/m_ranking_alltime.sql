
  
    

    create or replace table `training-assistant-prod`.`mart`.`m_ranking_alltime`
      
    
    

    OPTIONS()
    as (
      

WITH alltime_volume AS (
    SELECT
        f.user_id,
        u.user_name,
        SUM(f.volume) AS total_volume
    FROM `training-assistant-prod`.`mart`.`fct_training_set` f
    LEFT JOIN `training-assistant-prod`.`mart`.`d_user` u ON f.user_id = u.user_id
    GROUP BY 1, 2
)

SELECT
    *,
    RANK() OVER (ORDER BY total_volume DESC) AS rank
FROM alltime_volume
    );
  