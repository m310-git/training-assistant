-- ============================================================
-- Raw層テーブル定義（設計書v2準拠）
-- ============================================================
-- トレーニングログ（1セット=1レコード）
CREATE TABLE IF NOT EXISTS raw.training_log (
    log_id          STRING      NOT NULL,
    user_id         STRING      NOT NULL,
    exercise_name   STRING      NOT NULL,
    body_part       STRING      NOT NULL,
    training_date   DATE        NOT NULL,
    set_number      INT64       NOT NULL,
    weight_kg       FLOAT64     NOT NULL,
    reps            INT64       NOT NULL,
    rpe             FLOAT64,
    memo            STRING,
    input_source    STRING      NOT NULL,
    created_at      TIMESTAMP   NOT NULL,
    updated_at      TIMESTAMP   NOT NULL,
    is_deleted      BOOL        NOT NULL
)
PARTITION BY training_date
OPTIONS (
    description = '生トレーニングログ。1セット=1レコード。自動保存・編集対応。'
);
-- 種目マスタ
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
    description = '種目マスタ。管理者画面から管理。'
);
-- ユーザーマスタ
CREATE TABLE IF NOT EXISTS raw.user_master (
    user_id         STRING      NOT NULL,
    user_name       STRING      NOT NULL,
    line_user_id    STRING      NOT NULL,
    is_admin        BOOL        NOT NULL,
    is_active       BOOL        NOT NULL,
    created_at      TIMESTAMP   NOT NULL
)
OPTIONS (
    description = 'ユーザーマスタ。初期セットアップ時に手動投入。'
);
-- 種目追加リクエスト
CREATE TABLE IF NOT EXISTS raw.exercise_request (
    request_id      STRING      NOT NULL,
    user_id         STRING      NOT NULL,
    exercise_name   STRING      NOT NULL,
    body_part_id    STRING      NOT NULL,
    reason          STRING,
    status          STRING      NOT NULL,
    reviewed_by     STRING,
    created_at      TIMESTAMP   NOT NULL,
    reviewed_at     TIMESTAMP
)
OPTIONS (
    description = '種目追加リクエスト。全ユーザーが送信可能。'
);
-- 通知送信ログ
CREATE TABLE IF NOT EXISTS raw.notification_log (
    notification_id STRING      NOT NULL,
    user_id         STRING      NOT NULL,
    notification_type STRING    NOT NULL,
    status          STRING      NOT NULL,
    sent_at         TIMESTAMP   NOT NULL
)
OPTIONS (
    description = '通知送信ログ。LINE無料枠の管理に使用。'
);