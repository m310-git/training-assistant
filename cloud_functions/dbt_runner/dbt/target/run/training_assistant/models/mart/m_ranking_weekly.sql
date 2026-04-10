
  
    

    create or replace table `training-assistant-prod`.`mart`.`m_ranking_weekly`
      
    
    

    OPTIONS()
    as (
      

WITH weekly_volume AS (
    SELECT
        f.user_id,
        u.user_name,
        DATE_TRUNC(f.training_date, WEEK(MONDAY)) AS week_start,
        DATE_ADD(DATE_TRUNC(f.training_date, WEEK(MONDAY)), INTERVAL 6 DAY) AS week_end,
        SUM(f.volume) AS total_volume
    FROM `training-assistant-prod`.`mart`.`fct_training_set` f
    LEFT JOIN `training-assistant-prod`.`mart`.`d_user` u ON f.user_id = u.user_id
    GROUP BY 1, 2, 3, 4
),

ranked AS (
    SELECT
        *,
        RANK() OVER (
            PARTITION BY week_start
            ORDER BY total_volume DESC
        ) AS rank
    FROM weekly_volume
),

with_prev AS (
    SELECT
        r.*,
        LAG(r.rank) OVER (
            PARTITION BY r.user_id
            ORDER BY r.week_start
        ) AS prev_rank,
        LAG(r.total_volume) OVER (
            PARTITION BY r.user_id
            ORDER BY r.week_start
        ) AS prev_volume
    FROM ranked r
)

SELECT
    *,
    CASE
        WHEN prev_rank IS NULL THEN 'NEW'
        WHEN rank < prev_rank THEN 'UP'
        WHEN rank > prev_rank THEN 'DOWN'
        ELSE 'SAME'
    END AS rank_change,
    CASE
        WHEN prev_rank IS NULL THEN NULL
        ELSE prev_rank - rank
    END AS rank_diff
FROM with_prev
    );
  