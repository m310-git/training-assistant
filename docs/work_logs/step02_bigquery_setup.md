# Step 2: BigQueryセットアップ

## 概要

BigQueryにレイクハウス3層構造（raw, staging, mart）のデータセットを作成し、
Raw層テーブル5つの作成と初期データ（seed）投入を行う。

## 前提条件

- [ ] Step 1 完了
- [ ] GCPプロジェクト training-assistant-prod が有効
- [ ] BigQuery API が有効化済み

---

## 手順

### 2-1. データセット作成（3層構造）

    # Raw層: 生データ格納
    bq mk --dataset \
        --description="生データ格納層。Streamlitからの入力データ。" \
        --location=asia-northeast1 \
        training-assistant-prod:raw

    # Staging層: クレンジング済みデータ
    bq mk --dataset \
        --description="クレンジング済みデータ層。dbtで変換後のデータ。" \
        --location=asia-northeast1 \
        training-assistant-prod:staging

    # Mart層: 分析・アプリ参照用
    bq mk --dataset \
        --description="分析・アプリ参照用データ層。KPI計算後の最終集計データ。" \
        --location=asia-northeast1 \
        training-assistant-prod:mart

    # 確認
    bq ls

| データセット | 役割 | ロケーション |
|---|---|---|
| raw | 生データ格納 | asia-northeast1 |
| staging | クレンジング済みデータ | asia-northeast1 |
| mart | 分析・アプリ参照用 | asia-northeast1 |

3層構造の意味:

    raw     → 生データそのまま（何も加工しない）
    staging → クレンジング・型変換（きれいにする）
    mart    → 分析用に集計・結合（使いやすくする）

### 2-2. Raw層テーブル作成SQL

scripts/setup_bigquery.sql を作成:
---
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
---
### 2-3. テーブル作成実行

    bq query --use_legacy_sql=false < scripts/setup_bigquery.sql

    # 確認（5テーブルが表示されること）
    bq ls raw

期待結果:

         tableId          Type
    -------------------- -------
     exercise_master      TABLE
     exercise_request     TABLE
     notification_log     TABLE
     training_log         TABLE
     user_master          TABLE

### 2-4. 初期データ投入SQL作成

scripts/seed_data.sql を作成:

    -- ============================================================
    -- 初期データ投入（設計書v2準拠）
    -- ============================================================

    -- ユーザーマスタ（3名）
    INSERT INTO raw.user_master VALUES
        ('user_001', 'ユーザー1', 'U_LINE_ID_001', TRUE,  TRUE, CURRENT_TIMESTAMP()),
        ('user_002', 'ユーザー2', 'U_LINE_ID_002', FALSE, TRUE, CURRENT_TIMESTAMP()),
        ('user_003', 'ユーザー3', 'U_LINE_ID_003', FALSE, TRUE, CURRENT_TIMESTAMP());

    -- 種目マスタ（17種目: 5部位×3種目 + その他2種目）
    INSERT INTO raw.exercise_master VALUES
        -- 胸
        ('bench_press',       'ベンチプレス',             'chest',    TRUE,  TRUE, 1, CURRENT_TIMESTAMP()),
        ('incline_db_press',  'インクラインDBプレス',       'chest',    FALSE, TRUE, 2, CURRENT_TIMESTAMP()),
        ('cable_fly',         'ケーブルフライ',            'chest',    FALSE, TRUE, 3, CURRENT_TIMESTAMP()),
        -- 背中
        ('half_deadlift',     'ハーフデッドリフト',         'back',     TRUE,  TRUE, 1, CURRENT_TIMESTAMP()),
        ('lat_pulldown',      'ラットプルダウン',           'back',     FALSE, TRUE, 2, CURRENT_TIMESTAMP()),
        ('seated_row',        'シーテッドロウ',            'back',     FALSE, TRUE, 3, CURRENT_TIMESTAMP()),
        -- 肩
        ('overhead_press',    'オーバーヘッドプレス',       'shoulder', TRUE,  TRUE, 1, CURRENT_TIMESTAMP()),
        ('side_raise',        'サイドレイズ',              'shoulder', FALSE, TRUE, 2, CURRENT_TIMESTAMP()),
        ('face_pull',         'フェイスプル',              'shoulder', FALSE, TRUE, 3, CURRENT_TIMESTAMP()),
        -- 脚
        ('squat',             'スクワット',                'leg',      TRUE,  TRUE, 1, CURRENT_TIMESTAMP()),
        ('leg_press',         'レッグプレス',              'leg',      FALSE, TRUE, 2, CURRENT_TIMESTAMP()),
        ('leg_curl',          'レッグカール',              'leg',      FALSE, TRUE, 3, CURRENT_TIMESTAMP()),
        -- 腕
        ('barbell_curl',      'バーベルカール',            'arm',      FALSE, TRUE, 1, CURRENT_TIMESTAMP()),
        ('triceps_pushdown',  'トライセプスプッシュダウン',  'arm',      FALSE, TRUE, 2, CURRENT_TIMESTAMP()),
        ('hammer_curl',       'ハンマーカール',            'arm',      FALSE, TRUE, 3, CURRENT_TIMESTAMP()),
        -- その他
        ('plank',             'プランク',                  'other',    FALSE, TRUE, 1, CURRENT_TIMESTAMP()),
        ('ab_rollout',        'アブローラー',              'other',    FALSE, TRUE, 2, CURRENT_TIMESTAMP());

### 2-5. 初期データ投入実行

    bq query --use_legacy_sql=false < scripts/seed_data.sql

    # 確認
    bq query --use_legacy_sql=false \
        "SELECT user_id, user_name, is_admin FROM raw.user_master"

    bq query --use_legacy_sql=false \
        "SELECT exercise_id, exercise_name, body_part_id, is_compound
         FROM raw.exercise_master
         ORDER BY body_part_id, display_order"

期待結果（ユーザーマスタ）:

    | user_id  | user_name  | is_admin |
    |----------|------------|----------|
    | user_001 | ユーザー1   | true     |
    | user_002 | ユーザー2   | false    |
    | user_003 | ユーザー3   | false    |

期待結果（種目マスタ - 抜粋）:

    | exercise_id    | exercise_name        | body_part_id | is_compound |
    |----------------|----------------------|--------------|-------------|
    | barbell_curl   | バーベルカール        | arm          | false       |
    | half_deadlift  | ハーフデッドリフト     | back         | true        |
    | bench_press    | ベンチプレス          | chest        | true        |
    | squat          | スクワット           | leg          | true        |
    | plank          | プランク             | other        | false       |
    | ab_rollout     | アブローラー         | other        | false       |
    | overhead_press | オーバーヘッドプレス   | shoulder     | true        |

KPI対象種目（is_compound = TRUE）:

| 種目 | 部位 |
|---|---|
| ベンチプレス | chest |
| ハーフデッドリフト | back |
| オーバーヘッドプレス | shoulder |
| スクワット | leg |

### 2-6. テーブルスキーマ確認

    bq show --schema --format=prettyjson raw.training_log
    bq show --schema --format=prettyjson raw.exercise_master
    bq show --schema --format=prettyjson raw.user_master
    bq show --schema --format=prettyjson raw.exercise_request
    bq show --schema --format=prettyjson raw.notification_log

各テーブルのカラム数が以下と一致すること:

| テーブル | カラム数 | レコード数 |
|---|---|---|
| training_log | 14 | 0 |
| exercise_master | 7 | 17 |
| user_master | 6 | 3 |
| exercise_request | 9 | 0 |
| notification_log | 5 | 0 |

### 2-7. Gitコミット＆プッシュ

    git add scripts/setup_bigquery.sql scripts/seed_data.sql docs/work_logs/
    git commit -m "feat: BigQuery raw layer tables and seed data (design doc v2)"
    git push origin main

---

## 現在のBigQuery状態

    training-assistant-prod
    ├── raw（データセット）
    │   ├── training_log       # 14カラム / パーティション: DAY / 0件
    │   ├── exercise_master    # 7カラム / 17件（5部位×3 + その他2）
    │   ├── user_master        # 6カラム / 3件（※LINE IDは仮値）
    │   ├── exercise_request   # 9カラム / 0件
    │   └── notification_log   # 5カラム / 0件
    ├── staging（データセット）
    │   └── （テーブルなし → Step 4でdbtが作成）
    └── mart（データセット）
        └── （テーブルなし → Step 4でdbtが作成）

---

## 完了チェックリスト

- [ ] データセット 3つ作成済み（raw, staging, mart）
- [ ] Raw層テーブル 5つ作成済み
- [ ] training_log: 14カラム、パーティション(training_date)、0件
- [ ] exercise_master: 7カラム、17件
- [ ] user_master: 6カラム、3件（is_admin含む）
- [ ] exercise_request: 9カラム、0件
- [ ] notification_log: 5カラム、0件
- [ ] ユーザー1がis_admin=TRUE、他2名がFALSE
- [ ] 種目マスタにハーフデッドリフト（half_deadlift）が含まれる
- [ ] 種目マスタにother部位（plank, ab_rollout）が含まれる
- [ ] scripts/ 配下のSQLファイルがGitにpush済み

