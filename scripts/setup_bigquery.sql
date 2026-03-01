-- ============================================================
-- Raw層テーブル作成
-- ============================================================

-- トレーニングログ（メインテーブル）
-- Streamlitから1セットごとに書き込まれる
CREATE TABLE IF NOT EXISTS raw.training_log (
    log_id          STRING      NOT NULL,
    user_id         STRING      NOT NULL,
    exercise_name   STRING      NOT NULL,
    body_part       STRING      NOT NULL,
    training_date   DATE        NOT NULL,
    weight_kg       FLOAT64     NOT NULL,
    reps            INT64       NOT NULL,
    sets            INT64       NOT NULL,
    rpe             FLOAT64,
    memo            STRING,
    input_source    STRING      NOT NULL,
    created_at      TIMESTAMP   NOT NULL
)
PARTITION BY training_date
OPTIONS (
    description = '生トレーニングログ。Streamlitから直接書き込み。'
);

-- 種目マスタ
-- Streamlitのメニュー管理画面から書き込まれる
CREATE TABLE IF NOT EXISTS raw.exercise_master (
    exercise_id     STRING      NOT NULL,
    exercise_name   STRING      NOT NULL,
    body_part_id    STRING      NOT NULL,
    is_compound     BOOL        NOT NULL,
    is_active       BOOL        NOT NULL,
    display_order   INT64       NOT NULL,
    updated_at      TIMESTAMP   NOT NULL
)
OPTIONS (
    description = '種目マスタ。Streamlitのメニュー管理から書き込み。'
);

-- ユーザーマスタ
-- 初期セットアップ時に手動投入
CREATE TABLE IF NOT EXISTS raw.user_master (
    user_id         STRING      NOT NULL,
    user_name       STRING      NOT NULL,
    line_user_id    STRING      NOT NULL,
    is_active       BOOL        NOT NULL,
    created_at      TIMESTAMP   NOT NULL
)
OPTIONS (
    description = 'ユーザーマスタ。初期セットアップ時に手動投入。'
);
