
# Step 9:BigQuery ML

## 概要

BigQuery MLでトレーニング重量予測モデルを構築し、
dbtモデル（m_ml_suggestion）で予測結果を生成する。

## 前提条件

- [ ] Step 4 完了（fct_training_setにデータが存在する）
- [ ] テストデータが十分に蓄積されている（最低でも各種目10セッション以上が理想）

---

## 手順

### 9-1. 学習データの確認

    bq query --use_legacy_sql=false << 'EOF'
    WITH training_pairs AS (
        SELECT
            user_id, exercise_id, set_number, training_date,
            weight_kg, reps, volume, rpe,
            LAG(weight_kg) OVER w AS prev_weight_kg,
            LAG(reps) OVER w AS prev_reps,
            LAG(rpe) OVER w AS prev_rpe,
            LAG(volume) OVER w AS prev_volume,
            DATE_DIFF(training_date, LAG(training_date) OVER w, DAY) AS days_since_last,
            weight_kg AS next_weight_kg
        FROM mart.fct_training_set
        WINDOW w AS (
            PARTITION BY user_id, exercise_id, set_number
            ORDER BY training_date
        )
    )
    SELECT COUNT(*) AS total_pairs,
           COUNT(CASE WHEN prev_weight_kg IS NOT NULL AND days_since_last IS NOT NULL THEN 1 END) AS valid_pairs
    FROM training_pairs
    EOF

valid_pairs が十分な数（目安: 30以上）であることを確認。
少ない場合はテストデータを追加投入する。

### 9-2. テストデータ追加投入（データ不足の場合）

    bq query --use_legacy_sql=false << 'EOF'
    INSERT INTO raw.training_log VALUES
        -- user_001: ベンチプレス 過去データ（1/6, 1/10, 1/13）
        ('test-101', 'user_001', 'ベンチプレス', 'chest', '2025-01-06', 1, 72.5, 5, 7.5, NULL, 'streamlit', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), FALSE),
        ('test-102', 'user_001', 'ベンチプレス', 'chest', '2025-01-06', 2, 77.5, 3, 8.0, NULL, 'streamlit', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), FALSE),
        ('test-103', 'user_001', 'ベンチプレス', 'chest', '2025-01-06', 3, 82.5, 1, 9.0, NULL, 'streamlit', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), FALSE),
        ('test-104', 'user_001', 'ベンチプレス', 'chest', '2025-01-10', 1, 75.0, 5, 7.5, NULL, 'streamlit', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), FALSE),
        ('test-105', 'user_001', 'ベンチプレス', 'chest', '2025-01-10', 2, 80.0, 3, 8.0, NULL, 'streamlit', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), FALSE),
        ('test-106', 'user_001', 'ベンチプレス', 'chest', '2025-01-10', 3, 85.0, 1, 9.0, NULL, 'streamlit', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), FALSE),
        ('test-107', 'user_001', 'ベンチプレス', 'chest', '2025-01-13', 1, 75.0, 5, 7.5, NULL, 'streamlit', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), FALSE),
        ('test-108', 'user_001', 'ベンチプレス', 'chest', '2025-01-13', 2, 82.5, 3, 8.5, NULL, 'streamlit', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), FALSE),
        ('test-109', 'user_001', 'ベンチプレス', 'chest', '2025-01-13', 3, 85.0, 1, 9.0, NULL, 'streamlit', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), FALSE),

        -- user_002: ハーフデッドリフト 過去データ（1/7, 1/14, 1/17）
        ('test-201', 'user_002', 'ハーフデッドリフト', 'back', '2025-01-07', 1, 90.0, 5, 7.5, NULL, 'streamlit', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), FALSE),
        ('test-202', 'user_002', 'ハーフデッドリフト', 'back', '2025-01-07', 2, 100.0, 3, 8.0, NULL, 'streamlit', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), FALSE),
        ('test-203', 'user_002', 'ハーフデッドリフト', 'back', '2025-01-07', 3, 110.0, 1, 9.0, NULL, 'streamlit', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), FALSE),
        ('test-204', 'user_002', 'ハーフデッドリフト', 'back', '2025-01-14', 1, 95.0, 5, 8.0, NULL, 'streamlit', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), FALSE),
        ('test-205', 'user_002', 'ハーフデッドリフト', 'back', '2025-01-14', 2, 105.0, 3, 8.5, NULL, 'streamlit', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), FALSE),
        ('test-206', 'user_002', 'ハーフデッドリフト', 'back', '2025-01-14', 3, 115.0, 1, 9.5, NULL, 'streamlit', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), FALSE),
        ('test-207', 'user_002', 'ハーフデッドリフト', 'back', '2025-01-17', 1, 97.5, 5, 8.0, NULL, 'streamlit', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), FALSE),
        ('test-208', 'user_002', 'ハーフデッドリフト', 'back', '2025-01-17', 2, 107.5, 3, 8.5, NULL, 'streamlit', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), FALSE),
        ('test-209', 'user_002', 'ハーフデッドリフト', 'back', '2025-01-17', 3, 117.5, 1, 9.5, NULL, 'streamlit', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), FALSE),

        -- user_003: スクワット 過去データ（1/9, 1/13, 1/16）
        ('test-301', 'user_003', 'スクワット', 'leg', '2025-01-09', 1, 90.0, 8, 7.5, NULL, 'streamlit', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), FALSE),
        ('test-302', 'user_003', 'スクワット', 'leg', '2025-01-09', 2, 100.0, 5, 8.0, NULL, 'streamlit', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), FALSE),
        ('test-303', 'user_003', 'スクワット', 'leg', '2025-01-09', 3, 110.0, 3, 8.5, NULL, 'streamlit', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), FALSE),
        ('test-304', 'user_003', 'スクワット', 'leg', '2025-01-13', 1, 95.0, 8, 8.0, NULL, 'streamlit', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), FALSE),
        ('test-305', 'user_003', 'スクワット', 'leg', '2025-01-13', 2, 105.0, 5, 8.5, NULL, 'streamlit', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), FALSE),
        ('test-306', 'user_003', 'スクワット', 'leg', '2025-01-13', 3, 115.0, 3, 9.0, NULL, 'streamlit', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), FALSE),
        ('test-307', 'user_003', 'スクワット', 'leg', '2025-01-16', 1, 97.5, 8, 8.0, NULL, 'streamlit', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), FALSE),
        ('test-308', 'user_003', 'スクワット', 'leg', '2025-01-16', 2, 107.5, 5, 8.5, NULL, 'streamlit', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), FALSE),
        ('test-309', 'user_003', 'スクワット', 'leg', '2025-01-16', 3, 117.5, 3, 9.0, NULL, 'streamlit', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), FALSE)
    ;
    EOF

    # dbt run で mart を更新
    cd dbt
    dbt run

### 9-3. BigQuery MLモデル作成

    bq query --use_legacy_sql=false << 'EOF'
    CREATE OR REPLACE MODEL mart.training_predictor
    OPTIONS(
        model_type = 'BOOSTED_TREE_REGRESSOR',
        input_label_cols = ['next_weight_kg'],
        num_trials = 5,
        max_iterations = 50,
        early_stop = TRUE,
        data_split_method = 'AUTO_SPLIT'
    ) AS
    WITH training_pairs AS (
        SELECT
            user_id, exercise_id, set_number, training_date,
            weight_kg, reps, volume, rpe,
            LAG(weight_kg) OVER w AS prev_weight_kg,
            LAG(reps) OVER w AS prev_reps,
            LAG(rpe) OVER w AS prev_rpe,
            LAG(volume) OVER w AS prev_volume,
            DATE_DIFF(training_date, LAG(training_date) OVER w, DAY) AS days_since_last,
            weight_kg AS next_weight_kg
        FROM mart.fct_training_set
        WINDOW w AS (
            PARTITION BY user_id, exercise_id, set_number
            ORDER BY training_date
        )
    )
    SELECT
        prev_weight_kg, prev_reps, prev_rpe, prev_volume,
        set_number, days_since_last, next_weight_kg
    FROM training_pairs
    WHERE prev_weight_kg IS NOT NULL
      AND days_since_last IS NOT NULL
    EOF

※ モデル作成には数分かかる場合がある

### 9-4. モデル評価

    bq query --use_legacy_sql=false \
        "SELECT * FROM ML.EVALUATE(MODEL mart.training_predictor)"

期待結果:

    | mean_absolute_error | mean_squared_error | r2_score |
    |---------------------|--------------------|----------|
    | ≦ 5.0              | -                  | ≧ 0.7   |

※ データ量が少ない初期段階では r2_score が低くなる可能性がある
※ r2_score が 0.3 未満の場合はフォールバックロジックが主に使用される

### 9-5. 予測テスト

    bq query --use_legacy_sql=false << 'EOF'
    SELECT *
    FROM ML.PREDICT(
        MODEL mart.training_predictor,
        (
            SELECT
                weight_kg AS prev_weight_kg,
                reps AS prev_reps,
                rpe AS prev_rpe,
                volume AS prev_volume,
                set_number,
                7 AS days_since_last
            FROM mart.fct_training_set
            WHERE user_id = 'user_001'
              AND exercise_name = 'ベンチプレス'
            QUALIFY ROW_NUMBER() OVER (
                PARTITION BY set_number
                ORDER BY training_date DESC
            ) = 1
        )
    )
    EOF

予測結果が妥当な範囲（前回重量の±10%程度）であることを確認。

### 9-6. m_ml_suggestion dbtモデル作成

#### dbt/models/mart/m_ml_suggestion.sql

    {{
        config(materialized='table')
    }}

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
        FROM {{ ref('fct_training_set') }}
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
        ROUND(suggested_weight_kg, 1) AS suggested_weight_kg,
        suggested_reps,
        ROUND(suggested_weight_kg * suggested_reps, 1) AS suggested_volume,
        CURRENT_DATE('Asia/Tokyo') AS suggested_date,
        'boosted_tree_v1' AS model_version
    FROM predictions

### 9-7. schema.yml にML関連テストを追加

dbt/models/mart/schema.yml に以下を追記:

      - name: m_ml_suggestion
        description: "BigQuery ML予測結果。次回の推奨重量・回数。"
        columns:
          - name: user_id
            tests: [not_null]
          - name: exercise_id
            tests: [not_null]
          - name: suggested_weight_kg
            tests: [not_null]
          - name: suggested_reps
            tests: [not_null]
          - name: model_version
            tests: [not_null]

### 9-8. dbt run + test

    cd dbt
    dbt run
    dbt test

期待結果:

    dbt run: PASS=13（m_ml_suggestion が追加）
    dbt test: 全テストPASS

### 9-9. 予測結果の確認

    bq query --use_legacy_sql=false << 'EOF'
    SELECT
        user_id,
        exercise_name,
        set_number,
        current_weight_kg,
        current_reps,
        current_rpe,
        suggested_weight_kg,
        suggested_reps,
        suggested_volume
    FROM mart.m_ml_suggestion
    ORDER BY user_id, exercise_name, set_number
    EOF

確認項目:
- 各ユーザー・種目・セットごとに予測結果が存在する
- suggested_weight_kg が current_weight_kg の ±10% 程度の妥当な範囲
- suggested_reps が RPE に基づいて適切に設定されている
- suggested_volume が計算されている

### 9-10. Input画面のML提案表示を確認

    cd streamlit
    streamlit run app.py

確認項目:
- Input画面で種目を選択した際に「🤖 AIモデルによる提案」が表示される
- MLデータがない種目では「📈 過去実績ベースの提案」にフォールバックする
- 提案通りの総負荷量が表示される

### 9-11. Gitコミット＆プッシュ

    git add dbt/models/mart/m_ml_suggestion.sql dbt/models/mart/schema.yml docs/work_logs/
    git commit -m "feat: BigQuery ML model and suggestion table"
    git push origin main

---

## 現在のdbt構成（更新後）

    dbt/
    ├── dbt_project.yml
    ├── models/
    │   ├── staging/
    │   │   ├── sources.yml
    │   │   ├── schema.yml
    │   │   └── stg_training_log.sql
    │   └── mart/
    │       ├── schema.yml              ← m_ml_suggestion テスト追加
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
    │       ├── m_calendar.sql
    │       └── m_ml_suggestion.sql     ← 新規
    ├── seeds/
    ├── tests/
    └── macros/

---

## 完了チェックリスト

- [ ] 学習データが十分に存在する（valid_pairs ≧ 30）
- [ ] BigQuery MLモデル（mart.training_predictor）が作成されている
- [ ] モデル評価指標が確認できる（mean_absolute_error, r2_score）
- [ ] 予測テストで妥当な結果が返る
- [ ] m_ml_suggestion dbtモデルが作成されている
- [ ] dbt run で m_ml_suggestion が生成される
- [ ] dbt test が全てPASS
- [ ] Input画面でML提案が表示される
- [ ] フォールバック提案が動作する
- [ ] Gitにpush済み


