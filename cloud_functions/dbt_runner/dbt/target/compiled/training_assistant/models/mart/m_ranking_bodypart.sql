

WITH weekly AS (
    SELECT
        f.user_id,
        u.user_name,
        f.body_part_id,
        bp.body_part_name,
        'weekly' AS period_type,
        DATE_TRUNC(f.training_date, WEEK(MONDAY)) AS period_start,
        SUM(f.volume) AS total_volume
    FROM `training-assistant-prod`.`mart`.`fct_training_set` f
    LEFT JOIN `training-assistant-prod`.`mart`.`d_user` u ON f.user_id = u.user_id
    LEFT JOIN `training-assistant-prod`.`mart`.`d_body_part` bp ON f.body_part_id = bp.body_part_id
    GROUP BY 1, 2, 3, 4, 5, 6
),

monthly AS (
    SELECT
        f.user_id,
        u.user_name,
        f.body_part_id,
        bp.body_part_name,
        'monthly' AS period_type,
        DATE_TRUNC(f.training_date, MONTH) AS period_start,
        SUM(f.volume) AS total_volume
    FROM `training-assistant-prod`.`mart`.`fct_training_set` f
    LEFT JOIN `training-assistant-prod`.`mart`.`d_user` u ON f.user_id = u.user_id
    LEFT JOIN `training-assistant-prod`.`mart`.`d_body_part` bp ON f.body_part_id = bp.body_part_id
    GROUP BY 1, 2, 3, 4, 5, 6
),

alltime AS (
    SELECT
        f.user_id,
        u.user_name,
        f.body_part_id,
        bp.body_part_name,
        'alltime' AS period_type,
        CAST(NULL AS DATE) AS period_start,
        SUM(f.volume) AS total_volume
    FROM `training-assistant-prod`.`mart`.`fct_training_set` f
    LEFT JOIN `training-assistant-prod`.`mart`.`d_user` u ON f.user_id = u.user_id
    LEFT JOIN `training-assistant-prod`.`mart`.`d_body_part` bp ON f.body_part_id = bp.body_part_id
    GROUP BY 1, 2, 3, 4, 5, 6
),

combined AS (
    SELECT * FROM weekly
    UNION ALL
    SELECT * FROM monthly
    UNION ALL
    SELECT * FROM alltime
)

SELECT
    *,
    RANK() OVER (
        PARTITION BY body_part_id, period_type, period_start
        ORDER BY total_volume DESC
    ) AS rank
FROM combined