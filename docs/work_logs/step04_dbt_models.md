step04_dbt_models.md

# Step 4: dbtモデル作成

## 概要

staging層（クレンジング）とmart層（ディメンション・ファクト・メトリクス）の全dbtモデルを作成し、
dbt run + dbt test で動作確認する。

## 前提条件

- [ ] Step 3 完了
- [ ] dbt debug が全てPASS
- [ ] raw層に初期データ（seed）が投入済み

---

## 手順

### 4-1. Staging層モデル作成

#### dbt/models/staging/stg_training_log.sql

    {{
        config(
            materialized='incremental',
            unique_key='log_id',
            partition_by={
                "field": "training_date",
                "data_type": "date",
                "granularity": "month"
            }
        )
    }}

    WITH source AS (
        SELECT * FROM {{ source('raw', 'training_log') }}
        WHERE is_deleted = FALSE
        {% if is_incremental() %}
        AND updated_at > (SELECT MAX(updated_at) FROM {{ this }})
        {% endif %}
    ),

    deduplicated AS (
        SELECT
            *,
            ROW_NUMBER() OVER (
                PARTITION BY log_id
                ORDER BY updated_at DESC
            ) AS row_num
        FROM source
    ),

    cleaned AS (
        SELECT
            log_id,
            user_id,
            LOWER(TRIM(exercise_name))  AS exercise_name,
            LOWER(TRIM(body_part))      AS body_part,
            training_date,
            set_number,
            ROUND(weight_kg, 1)         AS weight_kg,
            reps,
            ROUND(weight_kg * reps, 1)  AS volume,
            CASE
                WHEN rpe BETWEEN 6.0 AND 10.0 THEN ROUND(rpe, 1)
                ELSE NULL
            END AS rpe,
            memo,
            created_at,
            updated_at
        FROM deduplicated
        WHERE row_num = 1
    )

    SELECT * FROM cleaned

#### dbt/models/staging/schema.yml

    version: 2

    models:
      - name: stg_training_log
        description: "クレンジング済みトレーニングログ"
        columns:
          - name: log_id
            tests: [unique, not_null]
          - name: user_id
            tests: [not_null]
          - name: weight_kg
            tests: [not_null]
          - name: reps
            tests: [not_null]
          - name: volume
            tests: [not_null]

### 4-2. Mart層 - ディメンションモデル作成

#### dbt/models/mart/d_body_part.sql

    {{
        config(materialized='table')
    }}

    SELECT * FROM UNNEST([
        STRUCT('chest'    AS body_part_id, '胸'    AS body_part_name, 'Monday'    AS training_day, 1 AS sort_order),
        STRUCT('back'     AS body_part_id, '背中'   AS body_part_name, 'Tuesday'   AS training_day, 2 AS sort_order),
        STRUCT('shoulder' AS body_part_id, '肩'    AS body_part_name, 'Wednesday' AS training_day, 3 AS sort_order),
        STRUCT('leg'      AS body_part_id, '脚'    AS body_part_name, 'Thursday'  AS training_day, 4 AS sort_order),
        STRUCT('arm'      AS body_part_id, '腕'    AS body_part_name, 'Friday'    AS training_day, 5 AS sort_order),
        STRUCT('other'    AS body_part_id, 'その他' AS body_part_name, CAST(NULL AS STRING) AS training_day, 6 AS sort_order)
    ])

#### dbt/models/mart/d_exercise.sql

    {{
        config(materialized='table')
    }}

    SELECT
        exercise_id,
        exercise_name,
        body_part_id,
        is_compound,
        is_active,
        display_order,
        updated_at
    FROM {{ source('raw', 'exercise_master') }}
    WHERE is_active = TRUE

#### dbt/models/mart/d_user.sql

    {{
        config(materialized='table')
    }}

    SELECT
        user_id,
        user_name,
        line_user_id,
        is_admin,
        is_active,
        created_at
    FROM {{ source('raw', 'user_master') }}
    WHERE is_active = TRUE

### 4-3. Mart層 - ファクトモデル作成

#### dbt/models/mart/fct_training_set.sql

    {{
        config(
            materialized='incremental',
            unique_key='log_id',
            partition_by={
                "field": "training_date",
                "data_type": "date",
                "granularity": "month"
            }
        )
    }}

    SELECT
        s.log_id,
        s.user_id,
        s.training_date,
        e.exercise_id,
        e.exercise_name,
        e.is_compound,
        bp.body_part_id,
        bp.body_part_name,
        s.set_number,
        s.weight_kg,
        s.reps,
        s.volume,
        s.rpe,
        s.memo,
        s.created_at
    FROM {{ ref('stg_training_log') }} s
    LEFT JOIN {{ ref('d_exercise') }} e
        ON LOWER(TRIM(s.exercise_name)) = LOWER(TRIM(e.exercise_name))
    LEFT JOIN {{ ref('d_body_part') }} bp
        ON LOWER(TRIM(s.body_part)) = bp.body_part_id

    {% if is_incremental() %}
    WHERE s.updated_at > (SELECT MAX(created_at) FROM {{ this }})
    {% endif %}

### 4-4. Mart層 - メトリクスモデル作成

#### dbt/models/mart/m_progress_curve.sql

    {{
        config(materialized='table')
    }}

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
        FROM {{ ref('fct_training_set') }}
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

#### dbt/models/mart/m_last_training.sql

    {{
        config(materialized='table')
    }}

    WITH last_per_body_part AS (
        SELECT
            user_id,
            body_part_id,
            body_part_name,
            MAX(training_date) AS last_training_date
        FROM {{ ref('fct_training_set') }}
        GROUP BY 1, 2, 3
    ),

    last_overall AS (
        SELECT
            user_id,
            MAX(training_date) AS last_training_date_any
        FROM {{ ref('fct_training_set') }}
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

#### dbt/models/mart/m_ranking_weekly.sql
    {{
        config(materialized='table')
    }}

    WITH weekly_volume AS (
        SELECT
            f.user_id,
            u.user_name,
            DATE_TRUNC(f.training_date, WEEK(MONDAY)) AS week_start,
            DATE_ADD(DATE_TRUNC(f.training_date, WEEK(MONDAY)), INTERVAL 6 DAY) AS week_end,
            SUM(f.volume) AS total_volume
        FROM {{ ref('fct_training_set') }} f
        LEFT JOIN {{ ref('d_user') }} u ON f.user_id = u.user_id
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

#### dbt/models/mart/m_ranking_monthly.sql

    {{
        config(materialized='table')
    }}

    WITH monthly_volume AS (
        SELECT
            f.user_id,
            u.user_name,
            DATE_TRUNC(f.training_date, MONTH) AS month,
            SUM(f.volume) AS total_volume
        FROM {{ ref('fct_training_set') }} f
        LEFT JOIN {{ ref('d_user') }} u ON f.user_id = u.user_id
        GROUP BY 1, 2, 3
    ),

    ranked AS (
        SELECT
            *,
            RANK() OVER (
                PARTITION BY month
                ORDER BY total_volume DESC
            ) AS rank
        FROM monthly_volume
    ),

    with_prev AS (
        SELECT
            r.*,
            LAG(r.rank) OVER (
                PARTITION BY r.user_id
                ORDER BY r.month
            ) AS prev_rank,
            LAG(r.total_volume) OVER (
                PARTITION BY r.user_id
                ORDER BY r.month
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

#### dbt/models/mart/m_ranking_alltime.sql

    {{
        config(materialized='table')
    }}

    WITH alltime_volume AS (
        SELECT
            f.user_id,
            u.user_name,
            SUM(f.volume) AS total_volume
        FROM {{ ref('fct_training_set') }} f
        LEFT JOIN {{ ref('d_user') }} u ON f.user_id = u.user_id
        GROUP BY 1, 2
    )

    SELECT
        *,
        RANK() OVER (ORDER BY total_volume DESC) AS rank
    FROM alltime_volume

#### dbt/models/mart/m_ranking_bodypart.sql

    {{
        config(materialized='table')
    }}

    WITH weekly AS (
        SELECT
            f.user_id,
            u.user_name,
            f.body_part_id,
            bp.body_part_name,
            'weekly' AS period_type,
            DATE_TRUNC(f.training_date, WEEK(MONDAY)) AS period_start,
            SUM(f.volume) AS total_volume
        FROM {{ ref('fct_training_set') }} f
        LEFT JOIN {{ ref('d_user') }} u ON f.user_id = u.user_id
        LEFT JOIN {{ ref('d_body_part') }} bp ON f.body_part_id = bp.body_part_id
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
        FROM {{ ref('fct_training_set') }} f
        LEFT JOIN {{ ref('d_user') }} u ON f.user_id = u.user_id
        LEFT JOIN {{ ref('d_body_part') }} bp ON f.body_part_id = bp.body_part_id
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
        FROM {{ ref('fct_training_set') }} f
        LEFT JOIN {{ ref('d_user') }} u ON f.user_id = u.user_id
        LEFT JOIN {{ ref('d_body_part') }} bp ON f.body_part_id = bp.body_part_id
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

#### dbt/models/mart/m_personal_record.sql

    {{
        config(materialized='table')
    }}

    WITH max_weight AS (
        SELECT
            user_id,
            exercise_id,
            exercise_name,
            'max_weight' AS record_type,
            MAX(weight_kg) AS record_value,
            ARRAY_AGG(training_date ORDER BY weight_kg DESC, training_date DESC LIMIT 1)[OFFSET(0)] AS achieved_date
        FROM {{ ref('fct_training_set') }}
        GROUP BY 1, 2, 3
    ),

    max_volume AS (
        SELECT
            user_id,
            exercise_id,
            exercise_name,
            'max_volume' AS record_type,
            MAX(volume) AS record_value,
            ARRAY_AGG(training_date ORDER BY volume DESC, training_date DESC LIMIT 1)[OFFSET(0)] AS achieved_date
        FROM {{ ref('fct_training_set') }}
        GROUP BY 1, 2, 3
    ),

    combined AS (
        SELECT * FROM max_weight
        UNION ALL
        SELECT * FROM max_volume
    ),

    with_previous AS (
        SELECT
            c.*,
            u.user_name,
            (
                SELECT MAX(
                    CASE
                        WHEN c.record_type = 'max_weight' THEN f.weight_kg
                        ELSE f.volume
                    END
                )
                FROM {{ ref('fct_training_set') }} f
                WHERE f.user_id = c.user_id
                  AND f.exercise_id = c.exercise_id
                  AND f.training_date < c.achieved_date
            ) AS previous_value,
            DATE_DIFF(CURRENT_DATE('Asia/Tokyo'), c.achieved_date, DAY) <= 7 AS is_new
        FROM combined c
        LEFT JOIN {{ ref('d_user') }} u ON c.user_id = u.user_id
    )

    SELECT
        user_id,
        user_name,
        exercise_id,
        exercise_name,
        record_type,
        record_value,
        achieved_date,
        previous_value,
        is_new
    FROM with_previous

#### dbt/models/mart/m_calendar.sql

    {{
        config(materialized='table')
    }}

    SELECT
        user_id,
        training_date,
        STRING_AGG(DISTINCT body_part_name, ', ' ORDER BY body_part_name) AS body_parts,
        SUM(volume) AS total_volume,
        COUNT(DISTINCT exercise_id) AS exercise_count,
        STRING_AGG(
            DISTINCT CONCAT(exercise_name, ': ', CAST(weight_kg AS STRING), 'kg'),
            ' / '
            ORDER BY exercise_name
        ) AS exercise_summary
    FROM {{ ref('fct_training_set') }}
    GROUP BY 1, 2

### 4-5. Mart層スキーマテスト定義

#### dbt/models/mart/schema.yml

    version: 2

    models:
      - name: d_body_part
        description: "部位マスタ（6部位）"
        columns:
          - name: body_part_id
            tests: [unique, not_null]

      - name: d_exercise
        description: "種目マスタ（有効のみ）"
        columns:
          - name: exercise_id
            tests: [unique, not_null]
          - name: body_part_id
            tests:
              - not_null
              - accepted_values:
                  values: ['chest', 'back', 'shoulder', 'leg', 'arm', 'other']

      - name: d_user
        description: "ユーザーマスタ（有効のみ）"
        columns:
          - name: user_id
            tests: [unique, not_null]

      - name: fct_training_set
        description: "トレーニングファクトテーブル"
        columns:
          - name: log_id
            tests: [unique, not_null]
          - name: user_id
            tests: [not_null]
          - name: volume
            tests: [not_null]

      - name: m_progress_curve
        description: "7日間移動平均・週次変化率（KPI）"
        columns:
          - name: user_id
            tests: [not_null]
          - name: exercise_id
            tests: [not_null]
          - name: metric_date
            tests: [not_null]

      - name: m_last_training
        description: "通知判定用（最終トレーニング日）"
        columns:
          - name: user_id
            tests: [not_null]
          - name: body_part_id
            tests: [not_null]

      - name: m_ranking_weekly
        description: "週間ボリュームランキング"
        columns:
          - name: rank
            tests: [not_null]

      - name: m_ranking_monthly
        description: "月間ボリュームランキング"
        columns:
          - name: rank
            tests: [not_null]

      - name: m_ranking_alltime
        description: "全期間ボリュームランキング"
        columns:
          - name: rank
            tests: [not_null]

      - name: m_ranking_bodypart
        description: "部位別ランキング"
        columns:
          - name: rank
            tests: [not_null]
          - name: period_type
            tests:
              - accepted_values:
                  values: ['weekly', 'monthly', 'alltime']

      - name: m_personal_record
        description: "個人記録・更新フラグ"
        columns:
          - name: record_type
            tests:
              - accepted_values:
                  values: ['max_weight', 'max_volume']

      - name: m_calendar
        description: "カレンダー表示用（日別サマリー）"
        columns:
          - name: user_id
            tests: [not_null]
          - name: training_date
            tests: [not_null]

### 4-6. テストデータ投入

動作確認用にraw.training_logにテストデータを投入:

    bq query --use_legacy_sql=false << 'EOF'
    INSERT INTO raw.training_log VALUES
        -- user_001: 2025/01/20 胸の日
        ('test-001', 'user_001', 'ベンチプレス', 'chest', '2025-01-20', 1, 80.0, 5, 8.0, NULL, 'streamlit', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), FALSE),
        ('test-002', 'user_001', 'ベンチプレス', 'chest', '2025-01-20', 2, 85.0, 3, 9.0, NULL, 'streamlit', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), FALSE),
        ('test-003', 'user_001', 'ベンチプレス', 'chest', '2025-01-20', 3, 90.0, 1, 9.5, NULL, 'streamlit', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), FALSE),
        ('test-004', 'user_001', 'インクラインDBプレス', 'chest', '2025-01-20', 1, 30.0, 10, 7.5, NULL, 'streamlit', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), FALSE),
        ('test-005', 'user_001', 'インクラインDBプレス', 'chest', '2025-01-20', 2, 32.5, 8, 8.0, NULL, 'streamlit', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), FALSE),

        -- user_002: 2025/01/20 背中の日
        ('test-006', 'user_002', 'ハーフデッドリフト', 'back', '2025-01-20', 1, 100.0, 5, 8.0, NULL, 'streamlit', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), FALSE),
        ('test-007', 'user_002', 'ハーフデッドリフト', 'back', '2025-01-20', 2, 110.0, 3, 8.5, NULL, 'streamlit', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), FALSE),
        ('test-008', 'user_002', 'ハーフデッドリフト', 'back', '2025-01-20', 3, 120.0, 1, 9.5, NULL, 'streamlit', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), FALSE),

        -- user_001: 2025/01/17 胸の日（過去データ: 進捗比較用）
        ('test-009', 'user_001', 'ベンチプレス', 'chest', '2025-01-17', 1, 77.5, 5, 8.0, NULL, 'streamlit', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), FALSE),
        ('test-010', 'user_001', 'ベンチプレス', 'chest', '2025-01-17', 2, 82.5, 3, 8.5, NULL, 'streamlit', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), FALSE),
        ('test-011', 'user_001', 'ベンチプレス', 'chest', '2025-01-17', 3, 87.5, 1, 9.5, NULL, 'streamlit', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), FALSE),

        -- user_003: 2025/01/20 脚の日
        ('test-012', 'user_003', 'スクワット', 'leg', '2025-01-20', 1, 100.0, 8, 8.0, NULL, 'streamlit', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), FALSE),
        ('test-013', 'user_003', 'スクワット', 'leg', '2025-01-20', 2, 110.0, 5, 8.5, NULL, 'streamlit', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), FALSE),
        ('test-014', 'user_003', 'スクワット', 'leg', '2025-01-20', 3, 120.0, 3, 9.0, NULL, 'streamlit', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), FALSE),
        ('test-015', 'user_003', 'レッグプレス', 'leg', '2025-01-20', 1, 150.0, 12, 7.5, NULL, 'streamlit', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), FALSE),
        ('test-016', 'user_003', 'レッグプレス', 'leg', '2025-01-20', 2, 160.0, 10, 8.0, NULL, 'streamlit', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), FALSE)
    ;
    EOF

    # 確認
    bq query --use_legacy_sql=false \
        "SELECT user_id, exercise_name, set_number, weight_kg, reps
         FROM raw.training_log
         ORDER BY user_id, training_date, exercise_name, set_number"

### 4-7. dbt run 実行

    cd dbt
    dbt run

期待結果:

    Completed successfully

    Done. PASS=12 WARN=0 ERROR=0 SKIP=0 TOTAL=12

生成されるテーブル:

    staging.stg_training_log
    mart.d_body_part
    mart.d_exercise
    mart.d_user
    mart.fct_training_set
    mart.m_progress_curve
    mart.m_last_training
    mart.m_ranking_weekly
    mart.m_ranking_monthly
    mart.m_ranking_alltime
    mart.m_ranking_bodypart
    mart.m_personal_record
    mart.m_calendar

### 4-8. dbt test 実行

    dbt test

期待結果:

    Completed successfully

    Done. PASS=XX WARN=0 ERROR=0 SKIP=0 TOTAL=XX

全テストがPASSすること。

### 4-9. データ確認クエリ

    -- staging層の確認
    bq query --use_legacy_sql=false \
        "SELECT COUNT(*) AS cnt FROM staging.stg_training_log"
    -- 期待: 16

    -- ファクトテーブルの確認
    bq query --use_legacy_sql=false \
        "SELECT COUNT(*) AS cnt FROM mart.fct_training_set"
    -- 期待: 16

    -- ディメンションの確認
    bq query --use_legacy_sql=false \
        "SELECT * FROM mart.d_body_part ORDER BY sort_order"
    -- 期待: 6行

    bq query --use_legacy_sql=false \
        "SELECT COUNT(*) AS cnt FROM mart.d_exercise"
    -- 期待: 17

    bq query --use_legacy_sql=false \
        "SELECT COUNT(*) AS cnt FROM mart.d_user"
    -- 期待: 3

    -- ランキングの確認
    bq query --use_legacy_sql=false \
        "SELECT * FROM mart.m_ranking_weekly ORDER BY week_start, rank"

    -- カレンダーの確認
    bq query --use_legacy_sql=false \
        "SELECT * FROM mart.m_calendar ORDER BY user_id, training_date"

    -- 個人記録の確認
    bq query --use_legacy_sql=false \
        "SELECT * FROM mart.m_personal_record ORDER BY user_id, exercise_name, record_type"

### 4-10. Gitコミット＆プッシュ

    git add dbt/models/ docs/work_logs/
    git commit -m "feat: all dbt models (staging + mart) with tests"
    git push origin main

---

## 現在のdbt構成

    dbt/
    ├── dbt_project.yml
    ├── models/
    │   ├── staging/
    │   │   ├── sources.yml
    │   │   ├── schema.yml
    │   │   └── stg_training_log.sql
    │   └── mart/
    │       ├── schema.yml
    │       ├── d_body_part.sql
    │       ├── d_exercise.sql
    │       ├── d_user.sql
    │       ├── fct_training_set.sql
    │       ├── m_progress_curve.sql
    │       ├── m_last_training.sql
    │       ├── m_ranking_weekly.sql
    │       ├── m_ranking_monthly.sql
    │       ├── m_ranking_alltime.sql
    │       ├── m_ranking_bodypart.sql
    │       ├── m_personal_record.sql
    │       └── m_calendar.sql
    ├── seeds/
    ├── tests/
    └── macros/

---

## 完了チェックリスト

- [ ] stg_training_log モデルが作成されている
- [ ] ディメンション 3モデル（d_body_part, d_exercise, d_user）が作成されている
- [ ] ファクト 1モデル（fct_training_set）が作成されている
- [ ] メトリクス 7モデルが作成されている
- [ ] schema.yml でテスト定義が完了している
- [ ] テストデータ 16件が投入されている
- [ ] dbt run が全モデル成功（PASS=12, ERROR=0）
- [ ] dbt test が全テスト成功（ERROR=0）
- [ ] staging層に16件、mart.fct_training_setに16件が存在する
- [ ] Gitにpush済み


    
