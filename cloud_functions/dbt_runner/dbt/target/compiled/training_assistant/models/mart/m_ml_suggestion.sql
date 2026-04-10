

WITH latest_per_set AS (
    SELECT
        user_id,
        exercise_id,
        exercise_name,
        set_number,
        weight_kg,
        reps,
        rpe,
        volume,
        training_date,
        DATE_DIFF(CURRENT_DATE('Asia/Tokyo'), training_date, DAY) AS days_since_last
    FROM `training-assistant-prod`.`mart`.`fct_training_set`
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY user_id, exercise_id, set_number
        ORDER BY training_date DESC
    ) = 1
),

predictions AS (
    SELECT
        p.user_id,
        p.exercise_id,
        p.exercise_name,
        p.set_number,
        p.weight_kg AS current_weight_kg,
        p.reps AS current_reps,
        p.rpe AS current_rpe,
        pred.predicted_next_weight_kg AS suggested_weight_kg,
        CASE
            WHEN p.rpe >= 9.5 THEN p.reps
            WHEN p.rpe <= 7.0 THEN p.reps + 2
            ELSE p.reps
        END AS suggested_reps,
        p.training_date AS last_training_date
    FROM latest_per_set p
    LEFT JOIN ML.PREDICT(
        MODEL `mart.training_predictor`,
        (
            SELECT
                user_id,
                exercise_id,
                set_number,
                weight_kg AS prev_weight_kg,
                reps AS prev_reps,
                rpe AS prev_rpe,
                volume AS prev_volume,
                days_since_last
            FROM latest_per_set
        )
    ) pred
    ON p.user_id = pred.user_id
    AND p.exercise_id = pred.exercise_id
    AND p.set_number = pred.set_number
)

SELECT
    user_id,
    exercise_id,
    exercise_name,
    set_number,
    current_weight_kg,
    current_reps,
    current_rpe,
    -- 前回重量を下回らないようにする
    ROUND(GREATEST(suggested_weight_kg, current_weight_kg), 1) AS suggested_weight_kg,
    suggested_reps,
    ROUND(GREATEST(suggested_weight_kg, current_weight_kg) * suggested_reps, 1) AS suggested_volume,
    CURRENT_DATE('Asia/Tokyo') AS suggested_date,
    'boosted_tree_v1' AS model_version
FROM predictions