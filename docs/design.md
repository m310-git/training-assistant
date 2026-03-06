# **設計書（改訂版 v2）：データ駆動型トレーニングアシスタント**

---

# **1. プロジェクト概要**

| **項目** | **詳細** |
| --- | --- |
| **プロジェクト名** | データ駆動型トレーニングアシスタント |
| **目的** | **実用＋学習のハイブリッド。** MVPは実用重視で最速構築し、拡張フェーズでモダンデータスタック・MLを段階導入する。 |
| **KPI** | 主要複合種目（ベンチプレス・スクワット・ハーフデッドリフト・オーバーヘッドプレス）の「7日間移動平均トレーニングボリューム（重量×回数×セット数）」の週次変化率を **≧ 1.0%** に維持する。毎週月曜日に前週分をローリング判定。 |
| **設計思想** | **費用最小化**（無料枠活用）、**段階的複雑化**（MVP→拡張）、**データ品質の担保**、**UXの最適化**（LINE通知＋ソーシャル機能）。 |
| **対象ユーザー** | 3名（個人＋トレーニング仲間） |

---

# **2. フェーズ計画**

| フェーズ | スコープ | 技術スタック | 期間目安 |
| --- | --- | --- | --- |
| Phase 1 (MVP) | 入力・変換・可視化・通知・ランキング・カレンダー・ソーシャル + BigQuery ML提案 | Streamlit + BigQuery + BigQuery ML + dbt Core + Cloud Functions + Cloud Scheduler | 3〜4週間 |
| Phase 2 (品質) | データ品質テストの強化・可視化 | + dbt-expectations + Elementary | 1〜2週間 |
| Phase 3 (自動化) | パイプラインオーケストレーション | + Prefect Cloud（Cloud Scheduler を置換） | 1週間 |
| Phase 4 (IaC) | インフラのコード化 | + Terraform（gcloudスクリプトを置換） | 1週間 |

> ***本設計書はPhase 1（MVP）を主軸に記述し、Phase 2〜5の拡張ポイントを各セクション末尾に付記する。***
> 

---

# **3. 技術スタックと選定理由**

### **3.1. Phase 1（MVP）構成**

| **コンポーネント** | **技術** | **役割** | **選定理由** |
| --- | --- | --- | --- |
| **DWH** | Google BigQuery | データ格納・分析 | サーバーレス。無料枠（10GB Storage / 1TB Query/月）で費用ゼロ運用可能。 |
| **変換** | dbt Core | データモデリング・集計 | SQLベースの宣言的変換。incremental modelでBQ無料枠を保護。OSS。 |
| **入力/可視化** | Streamlit Cloud | データ入力UI・ダッシュボード・ソーシャル機能 | 入力・可視化・ランキング・カレンダーを1アプリに集約。無料枠で運用可能。 |
| **通知ロジック** | Cloud Functions (2nd gen) | リマインド・ランキング通知送信 | イベント駆動型。無料枠（200万回/月）で十分。 |
| **スケジューラ** | Cloud Scheduler | 日次・週次・月次バッチ起動 | cron式でバッチジョブを実行。無料枠（3ジョブ）。 |
| **通知サービス** | LINE Messaging API | ユーザー通知 | 高い到達率。無料枠200通/月。 |
| **シークレット管理** | GCP Secret Manager | 認証情報の安全な格納 | APIキー・接続情報をコードから分離。 |
| **ML** | **BigQuery ML** | トレーニング提案（重量・回数予測） | BQ内完結。dbt統合で自動化。追加サービス・追加コスト不要。 |

### **3.2. Phase 2〜5 追加コンポーネント**

| Phase | 追加技術 | 置換対象 | 目的 |
| --- | --- | --- | --- |
| 2 | dbt-expectations + Elementary | dbt tests（組み込み）を拡張 | 60+テスト追加。テスト結果可視化・異常検知自動化。 |
| 3 | Prefect Cloud | Cloud Scheduler | ワークフローオーケストレーション |
| 4 | Terraform | gcloudスクリプト | IaCによるインフラ管理 |

---

# **4. システムアーキテクチャ**

### **4.1. Phase 1 アーキテクチャ図**

```
┌─────────────────────────────────────────────────────────────────────┐
│                        ユーザー (3名)                                │
│                     LINE / ブラウザ                                   │
└──────┬──────────────────────────┬────────────────────────────────────┘
       │                          │
       ▼                          ▼
┌──────────────┐          ┌───────────────────────┐
│  LINE App    │◄─────────│    Streamlit Cloud     │
│  (通知受信)   │  URL     ├───────────────────────┤
└──────────────┘  リンク   │ • 認証 (パスワード)     │
       ▲                  │ • トレーニング入力       │
       │                  │ • カレンダー表示         │
       │                  │ • プランナー（過去実績）  │
       │                  │ • ダッシュボード         │
       │                  │ • ランキング（週/月/全期間）│
       │                  │ • 他ユーザーの記録閲覧    │
       │                  │ • 記録更新フィード        │
       │                  │ • 種目追加リクエスト      │
       │                  │ • メニュー管理（管理者）   │
       │                  └────────┬──────────────┘
       │                           │ 書き込み/読み取り
       │                           ▼
       │                  ┌───────────────────────┐
       │                  │   Google BigQuery      │
       │                  ├───────────────────────┤
       │                  │ raw (生データ)          │
       │                  │ staging (変換済)        │
       │                  │ mart (分析用)           │
       │                  └────────┬──────────────┘
       │                           │
       │                  ┌────────┴──────────────┐
       │                  │                        │
       │                  ▼                        ▼
       │         ┌─────────────┐         ┌─────────────────┐
       │         │  dbt Core   │         │ Cloud Functions  │
       │         │ (日次変換)   │         │ (通知判定/送信)   │
       │         └──────┬──────┘         └────────┬────────┘
       │                │                         │
       │                └────────┬────────────────┘
       │                         │ 起動
       │                         ▼
       │                ┌─────────────────┐
       │                │ Cloud Scheduler  │──── Secret Manager
       │                │ (日次/週次/月次)  │     (LINE API Key等)
       │                └─────────────────┘
       │                         │
       └─────────────────────────┘
                  LINE Messaging API

```

### **4.2. 主要データフロー**

| **#** | **フロー名** | **経路** | **トリガー** |
| --- | --- | --- | --- |
| 1 | データ入力 | Streamlit → BigQuery `raw.training_log` | ユーザー操作 |
| 2 | 種目追加リクエスト | Streamlit → BigQuery `raw.exercise_request` | ユーザー操作 |
| 3 | 種目承認 | Streamlit（管理者）→ BigQuery `raw.exercise_master` | 管理者操作 |
| 4 | データ変換 | Cloud Scheduler → Cloud Functions → dbt → BigQuery `staging`/`mart` | 日次 06:00 JST |
| 5 | 日次通知判定 | Cloud Scheduler → Cloud Functions → `mart` 参照 → LINE | 日次 07:00 JST |
| 6 | 週間ランキング通知 | Cloud Scheduler → Cloud Functions → `mart` 参照 → LINE | 毎週月曜 08:00 JST |
| 7 | 月間ランキング通知 | Cloud Scheduler → Cloud Functions → `mart` 参照 → LINE | 毎月1日 08:00 JST |
| 8 | 筋トレ開始通知 | Streamlit → Cloud Functions → LINE | ユーザー操作 |
| 9 | 可視化 | Streamlit → BigQuery `mart` → グラフ/カレンダー/ランキング表示 | ユーザー操作 |

---

# **5. データモデリング**

### **5.1. レイクハウス3層構造**

| **レイヤー** | **データセット** | **役割** | **書き込み元** | **dbtモデル** |
| --- | --- | --- | --- | --- |
| **Raw** | `raw` | 生データ格納 | Streamlit | - |
| **Staging** | `staging` | クレンジング・型変換・重複排除 | dbt | `stg_training_log` |
| **Mart** | `mart` | 分析・アプリ参照用 | dbt | `fct_training_set`, `d_exercise`, `d_body_part`, `d_user`, `m_progress_curve`, `m_last_training`, `m_ranking_weekly`, `m_ranking_monthly`, `m_ranking_alltime`, `m_ranking_bodypart`, `m_personal_record`, `m_calendar` ,`ml_training_predictor`, `m_ml_suggestion` |

### **5.2. ER図**

```
┌──────────────┐     ┌───────────────────┐     ┌────────────────┐
│   d_user     │     │ fct_training_set  │     │  d_exercise    │
├──────────────┤     ├───────────────────┤     ├────────────────┤
│PK user_id    │◄──┐ │PK log_id          │ ┌──►│PK exercise_id  │
│  user_name   │   └─│FK user_id         │ │   │  exercise_name │
│  line_user_id│     │FK exercise_id     │─┘   │FK body_part_id │──┐
│  is_admin    │     │FK body_part_id    │─┐   │  is_compound   │  │
│  is_active   │     │  training_date    │ │   │  is_active     │  │
│  created_at  │     │  weight_kg        │ │   │  display_order │  │
└──────────────┘     │  reps             │ │   │  updated_at    │  │
                     │  sets             │ │   └────────────────┘  │
                     │  volume           │ │                        │
                     │  rpe              │ │   ┌────────────────┐  │
                     │  memo             │ │   │  d_body_part   │  │
                     │  created_at       │ │   ├────────────────┤  │
                     └───────────────────┘ │   │PK body_part_id │◄─┘
                                           └──►│  body_part_name│
                                               │  training_day  │
┌───────────────────┐                          │  sort_order    │
│ exercise_request  │                          └────────────────┘
├───────────────────┤
│PK request_id      │
│FK user_id         │
│  exercise_name    │
│  body_part_id     │
│  reason           │
│  status           │
│  reviewed_by      │
│  created_at       │
│  reviewed_at      │
└───────────────────┘

┌───────────────────┐     ┌───────────────────┐     ┌───────────────────┐
│ m_ranking_weekly  │     │ m_ranking_monthly │     │ m_ranking_alltime │
├───────────────────┤     ├───────────────────┤     ├───────────────────┤
│  user_id          │     │  user_id          │     │  user_id          │
│  user_name        │     │  user_name        │     │  user_name        │
│  week_start       │     │  month            │     │  total_volume     │
│  week_end         │     │  total_volume     │     │  rank             │
│  total_volume     │     │  rank             │     └───────────────────┘
│  rank             │     └───────────────────┘
└───────────────────┘
                          ┌───────────────────┐     ┌───────────────────┐
┌───────────────────┐     │ m_personal_record │     │   m_calendar      │
│m_ranking_bodypart │     ├───────────────────┤     ├───────────────────┤
├───────────────────┤     │  user_id          │     │  user_id          │
│  user_id          │     │  exercise_id      │     │  training_date    │
│  user_name        │     │  exercise_name    │     │  body_parts       │
│  body_part_id     │     │  record_type      │     │  total_volume     │
│  body_part_name   │     │  record_value     │     │  exercise_count   │
│  period_type      │     │  achieved_date    │     │  exercise_summary │
│  period_start     │     │  previous_value   │     └───────────────────┘
│  total_volume     │     │  is_new           │
│  rank             │     └───────────────────┘     ┌───────────────────┐
└───────────────────┘                               │ m_last_training   │
                                                    ├───────────────────┤
                                                    │  user_id          │
                                                    │  body_part_id     │
                                                    │  body_part_name   │
                                                    │  last_date        │
                                                    │  days_since_last  │
                                                    │  needs_3day       │
                                                    │  needs_7day       │
                                                    └───────────────────┘
┌───────────────────────┐
│ ml_training_predictor │  ← BigQuery MLモデル（テーブルではない）
├───────────────────────┤
│  model_type:          │
│  BOOSTED_TREE_REGRESSOR
│  input: prev_weight,  │
│    prev_reps, prev_rpe│
│    set_number         │
│  output:              │
│    predicted_weight   │
└───────────────────────┘

┌───────────────────────┐
│   m_ml_suggestion     │  ← 予測結果テーブル
├───────────────────────┤
│  user_id              │
│  exercise_id          │
│  exercise_name        │
│  set_number           │
│  current_weight_kg    │
│  current_reps         │
│  current_rpe          │
│  suggested_weight_kg  │
│  suggested_reps       │
│  confidence           │
│  model_version        │
│  suggested_date       │
└───────────────────────┘

```

### **5.3. テーブル定義**

### **Raw層**

| **テーブル** | **用途** | **書き込み元** |
| --- | --- | --- |
| `raw.training_log` | トレーニング記録 | Streamlit |
| `raw.exercise_master` | 種目マスタ | Streamlit（管理者） |
| `raw.user_master` | ユーザーマスタ | 初期セットアップ |
| `raw.exercise_request` | 種目追加リクエスト | Streamlit（全ユーザー） |

sql

### **Staging層（dbtモデル）**

| **モデル** | **用途** |
| --- | --- |
| `stg_training_log` | トレーニングログのクレンジング・重複排除・ボリューム計算 |

sql

```sql
-- ============================================================
-- models/staging/stg_training_log.sql（修正版：論理削除対応）
-- ============================================================
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

-- クレンジング、重複排除、ボリューム計算
-- 詳細は作業ログ Step 3 参照

```

```sql
-- ============================================================
-- raw.training_log（修正版：編集対応）
-- ============================================================
CREATE TABLE IF NOT EXISTS raw.training_log (
    log_id          STRING      NOT NULL,   -- UUID v4（セットごとに一意）
    user_id         STRING      NOT NULL,
    exercise_name   STRING      NOT NULL,
    body_part       STRING      NOT NULL,
    training_date   DATE        NOT NULL,
    set_number      INT64       NOT NULL,   -- セット番号（1, 2, 3...）
    weight_kg       FLOAT64     NOT NULL,
    reps            INT64       NOT NULL,
    rpe             FLOAT64,                -- 6.0-10.0, nullable
    memo            STRING,
    input_source    STRING      NOT NULL,
    created_at      TIMESTAMP   NOT NULL,   -- 初回作成日時
    updated_at      TIMESTAMP   NOT NULL,   -- 最終更新日時
    is_deleted      BOOL        NOT NULL DEFAULT FALSE  -- 論理削除フラグ
)
PARTITION BY training_date
OPTIONS (
    description = '生トレーニングログ。1セット=1レコード。自動保存・編集対応。'
);

-- raw.exercise_master（既存・変更なし）
CREATE TABLE IF NOT EXISTS raw.exercise_master (
    exercise_id     STRING      NOT NULL,
    exercise_name   STRING      NOT NULL,
    body_part_id    STRING      NOT NULL,
    is_compound     BOOL        NOT NULL,
    is_active       BOOL        NOT NULL,
    display_order   INT64       NOT NULL,
    updated_at      TIMESTAMP   NOT NULL
);

-- raw.user_master（is_admin カラム追加）
CREATE TABLE IF NOT EXISTS raw.user_master (
    user_id         STRING      NOT NULL,
    user_name       STRING      NOT NULL,
    line_user_id    STRING      NOT NULL,
    is_admin        BOOL        NOT NULL,   -- 管理者フラグ（種目承認権限）
    is_active       BOOL        NOT NULL,
    created_at      TIMESTAMP   NOT NULL
);

-- raw.exercise_request（新規：種目追加リクエスト）
CREATE TABLE IF NOT EXISTS raw.exercise_request (
    request_id      STRING      NOT NULL,   -- UUID v4
    user_id         STRING      NOT NULL,   -- リクエストしたユーザー
    exercise_name   STRING      NOT NULL,   -- 提案する種目名
    body_part_id    STRING      NOT NULL,   -- 部位
    reason          STRING,                 -- 追加理由（任意）
    status          STRING      NOT NULL,   -- pending / approved / rejected
    reviewed_by     STRING,                 -- 承認/却下した管理者のuser_id
    created_at      TIMESTAMP   NOT NULL,
    reviewed_at     TIMESTAMP               -- 承認/却下日時
);

```

### **Mart層（dbtモデル）**

### **ディメンションテーブル**

| **モデル** | **用途** |
| --- | --- |
| `d_body_part` | 部位マスタ（5分割法） |
| `d_exercise` | 種目マスタ（有効な種目のみ） |
| `d_user` | ユーザーマスタ（有効なユーザーのみ） |

### **ファクトテーブル**

| **モデル** | **用途** |
| --- | --- |
| `fct_training_set` | トレーニング記録（ディメンション結合済み） |

### **メトリクステーブル**

| **モデル** | **用途** | **参照元** |
| --- | --- | --- |
| `m_progress_curve` | 7日間移動平均ボリューム・週次変化率（KPI） | ダッシュボード |
| `m_last_training` | 最終トレーニング日・通知フラグ | Cloud Functions（通知判定） |
| `m_ranking_weekly` | 週間ボリュームランキング | ランキング画面・LINE通知 |
| `m_ranking_monthly` | 月間ボリュームランキング | ランキング画面・LINE通知 |
| `m_ranking_alltime` | 全期間ボリュームランキング | ランキング画面 |
| `m_ranking_bodypart` | 部位別ランキング（週/月/全期間） | ランキング画面 |
| `m_personal_record` | 個人記録（最高重量・最高ボリューム）・更新フラグ | 記録更新フィード |
| `m_calendar` | カレンダー表示用（日別サマリー） | カレンダー画面 |

### **新規Martモデル SQL定義**

sql

```sql
-- ============================================================
-- models/mart/m_ranking_weekly.sql
-- 週間ボリュームランキング（締日: 日曜日）
-- ============================================================
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
)

SELECT
    *,
    RANK() OVER (
        PARTITION BY week_start
        ORDER BY total_volume DESC
    ) AS rank
FROM weekly_volume

```

sql

```sql
-- ============================================================
-- models/mart/m_ranking_monthly.sql
-- 月間ボリュームランキング（締日: 末日）
-- ============================================================
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
)

SELECT
    *,
    RANK() OVER (
        PARTITION BY month
        ORDER BY total_volume DESC
    ) AS rank
FROM monthly_volume

```

sql

```sql
-- ============================================================
-- models/mart/m_ranking_alltime.sql
-- 全期間ボリュームランキング
-- ============================================================
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

```

sql

```sql
-- ============================================================
-- models/mart/m_ranking_bodypart.sql
-- 部位別ランキング（週/月/全期間）
-- ============================================================
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

```

```jsx
-- ============================================================
-- models/mart/m_personal_record.sql
-- 個人記録（最高重量・最高ボリューム）と更新フラグ
-- ============================================================
{{
    config(materialized='table')
}}

WITH max_weight AS (
    -- 種目ごとの最高重量
    SELECT
        user_id,
        exercise_id,
        exercise_name,
        'max_weight' AS record_type,
        MAX(weight_kg) AS record_value,
        -- 最高重量を記録した日
        ARRAY_AGG(training_date ORDER BY weight_kg DESC, training_date DESC LIMIT 1)[OFFSET(0)] AS achieved_date
    FROM {{ ref('fct_training_set') }}
    GROUP BY 1, 2, 3
),

max_volume AS (
    -- 種目ごとの1セット最高ボリューム
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
        -- 前回の記録値（直近7日以内に更新されたか判定用）
        -- 7日より前のデータだけで最大値を取る
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
              AND f.training_date < DATE_SUB(c.achieved_date, INTERVAL 0 DAY)
              AND f.training_date < c.achieved_date
        ) AS previous_value,
        -- 直近7日以内に達成されたか（フィード表示用）
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

```

```jsx
-- ============================================================
-- models/mart/m_calendar.sql
-- カレンダー表示用（日別サマリー）
-- ============================================================
{{
    config(materialized='table')
}}

SELECT
    user_id,
    training_date,

    -- その日にトレーニングした部位一覧（カンマ区切り）
    STRING_AGG(DISTINCT body_part_name, ', ' ORDER BY body_part_name) AS body_parts,

    -- その日の総ボリューム
    SUM(volume) AS total_volume,

    -- その日の種目数
    COUNT(DISTINCT exercise_id) AS exercise_count,

    -- その日の種目サマリー（クリック時の詳細表示用）
    STRING_AGG(
        DISTINCT CONCAT(exercise_name, ': ', CAST(weight_kg AS STRING), 'kg'),
        ' / '
        ORDER BY exercise_name
    ) AS exercise_summary

FROM {{ ref('fct_training_set') }}
GROUP BY 1, 2

```

```jsx
-- ============================================================
-- models/mart/m_last_training.sql（既存・変更なし）
-- 通知判定用: 最終トレーニング日と経過日数
-- ============================================================
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

    DATE_DIFF(CURRENT_DATE('Asia/Tokyo'), bp.last_training_date, DAY) >= 7
        AS needs_7day_reminder

FROM last_per_body_part bp
LEFT JOIN last_overall o
    ON bp.user_id = o.user_id

```

**新規dbtモデル SQL定義**

```jsx
-- ============================================================
-- models/mart/ml_training_predictor.sql
-- BigQuery MLモデル定義（週次で再学習）
-- ============================================================

-- ※ dbtではCREATE MODELを直接実行できないため
--   dbt run-operation または Cloud Functions から実行
--   以下はSQL定義のみ

CREATE OR REPLACE MODEL mart.training_predictor
OPTIONS(
    model_type = 'BOOSTED_TREE_REGRESSOR',
    input_label_cols = ['next_weight_kg'],
    auto_class_weights = TRUE,
    num_trials = 5,
    max_iterations = 50,
    early_stop = TRUE,
    data_split_method = 'AUTO_SPLIT'
) AS

WITH training_pairs AS (
    SELECT
        user_id,
        exercise_id,
        set_number,
        training_date,
        weight_kg,
        reps,
        volume,
        rpe,
        -- 前回の記録（特徴量）
        LAG(weight_kg) OVER w AS prev_weight_kg,
        LAG(reps) OVER w AS prev_reps,
        LAG(rpe) OVER w AS prev_rpe,
        LAG(volume) OVER w AS prev_volume,
        -- 前回からの経過日数
        DATE_DIFF(
            training_date,
            LAG(training_date) OVER w,
            DAY
        ) AS days_since_last,
        -- 目的変数（今回の重量）
        weight_kg AS next_weight_kg
    FROM mart.fct_training_set
    WINDOW w AS (
        PARTITION BY user_id, exercise_id, set_number
        ORDER BY training_date
    )
)

SELECT
    prev_weight_kg,
    prev_reps,
    prev_rpe,
    prev_volume,
    set_number,
    days_since_last,
    next_weight_kg
FROM training_pairs
WHERE prev_weight_kg IS NOT NULL
  AND days_since_last IS NOT NULL;

```

```jsx
-- ============================================================
-- models/mart/m_ml_suggestion.sql
-- BigQuery ML予測結果テーブル
-- ============================================================
{{
    config(materialized='table')
}}

WITH latest_per_set AS (
    -- 各ユーザー・種目・セットの最新レコード
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
        -- 回数の提案（RPEベース）
        CASE
            WHEN p.rpe >= 9.5 THEN p.reps  -- きつかった → 回数維持
            WHEN p.rpe <= 7.0 THEN p.reps + 2  -- 余裕あり → 回数増
            ELSE p.reps  -- 通常 → 回数維持
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
    -- 提案の総負荷量
    ROUND(suggested_weight_kg * suggested_reps, 1) AS suggested_volume,
    CURRENT_DATE('Asia/Tokyo') AS suggested_date,
    'boosted_tree_v1' AS model_version
FROM predictions

```

### **5.4. Mart層スキーマテスト定義**

yaml

```yaml
# ============================================================
# models/mart/schema.yml
# ============================================================
version: 2

models:
  - name: fct_training_set
    description: "トレーニングファクトテーブル（ディメンション結合済み）"
    columns:
      - name: log_id
        tests: [unique, not_null]
      - name: user_id
        tests: [not_null]
      - name: volume
        tests: [not_null]

  - name: d_body_part
    description: "部位マスタ（5分割法）"
    columns:
      - name: body_part_id
        tests: [unique, not_null]

  - name: d_exercise
    description: "種目マスタ（有効な種目のみ）"
    columns:
      - name: exercise_id
        tests: [unique, not_null]
      - name: body_part_id
        tests:
          - not_null
          - accepted_values:
              values: ['chest', 'back', 'shoulder', 'leg', 'arm']

  - name: d_user
    description: "ユーザーマスタ（有効なユーザーのみ）"
    columns:
      - name: user_id
        tests: [unique, not_null]

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
    description: "部位別ランキング（週/月/全期間）"
    columns:
      - name: rank
        tests: [not_null]

  - name: m_personal_record
    description: "個人記録と更新フラグ"
    columns:
      - name: record_type
        tests:
          - accepted_values:
              values: ['max_weight', 'max_volume']

  - name: m_calendar
    description: "カレンダー表示用（日別サマリー）"
    columns:
      - name: training_date
        tests: [not_null]

  - name: m_last_training
    description: "通知判定用（最終トレーニング日）"
    columns:
      - name: user_id
        tests: [not_null]

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
```

---

# **6. アプリケーション要件**

### **6.1. Streamlit アプリケーション画面構成**

```
streamlit/
├── app.py                      # メインページ（認証）
├── pages/
│   ├── 1_📝_Input.py           # トレーニング入力 + 過去実績 + 提案
│   ├── 2_📅_Calendar.py        # カレンダー
│   ├── 3_📊_Dashboard.py       # ダッシュボード（KPI）
│   ├── 4_🏆_Ranking.py         # ランキング
│   ├── 5_👥_Social.py          # 他ユーザーの記録・記録更新フィード
│   ├── 6_➕_ExerciseRequest.py  # 種目追加リクエスト
│   └── 7_⚙️_Admin.py           # 管理者画面（種目承認・メニュー管理）
└── utils/
    ├── auth.py
    ├── bigquery_client.py
    └── validators.py

```

### **6.2. 各画面の機能詳細**

### **1. トレーニング入力（Input）**

| **機能** | **詳細** |
| --- | --- |
| 部位選択 | セレクトボックス（胸/背中/肩/脚/腕/その他） |
| 種目選択 | 選択した部位に紐づく種目をセレクトボックスで表示 |
| 入力項目 | 日付、セットごとの重量(kg)・回数・RPE（任意）・メモ（任意） |
| セット管理 | 「セット追加」ボタンでセット行を動的に追加。セットごとに個別入力。 |
| 自動保存 | フォーカスが外れたタイミングで自動保存。保存済みセットに ✅ 表示。 |
| 当日復元 | 同日・同種目の既存記録があれば自動で復元し、編集を継続可能。 |
| 編集制限 | 記録作成から3時間以内のみ編集可能。超過後は読み取り専用。 |
| 休憩タイマー | セット間の休憩時間を計測。プリセット＋カスタム設定。 |
| 過去実績表示 | 選択した種目の直近3回分の記録をセット単位で表示 |
| 今回の提案 | 過去実績に基づく重量・回数の提案＋提案通りの場合の総負荷量を表示 |
| リアルタイム総負荷量 | セット入力中に現在の総負荷量をリアルタイムで計算・表示 |
| バリデーション | 重量: 0〜500kg、回数: 1〜100、RPE: 6.0〜10.0 |
| 筋トレ開始通知 | その日初回の記録登録時にLINEへ自動通知（アプリURLリンク付き） |
| データソース | `raw.training_log`, `mart.fct_training_set`, `mart.d_exercise` |

```jsx
# streamlit/pages/1_📝_Input.py の提案取得ロジック（疑似コード）

def get_suggestion(user_id, exercise_id):
    # 1. BigQuery MLの予測結果を取得
    ml_suggestion = query_bigquery(f"""
        SELECT set_number, suggested_weight_kg, suggested_reps, suggested_volume
        FROM mart.m_ml_suggestion
        WHERE user_id = '{user_id}'
          AND exercise_id = '{exercise_id}'
        ORDER BY set_number
    """)

    if ml_suggestion is not None and len(ml_suggestion) > 0:
        # MLの予測結果がある → そのまま使用
        return ml_suggestion, "ml"

    # 2. フォールバック: SQL単純提案（前回+2.5%）
    last_record = query_bigquery(f"""
        SELECT set_number, weight_kg, reps, rpe
        FROM mart.fct_training_set
        WHERE user_id = '{user_id}'
          AND exercise_id = '{exercise_id}'
        QUALIFY ROW_NUMBER() OVER (
            PARTITION BY set_number
            ORDER BY training_date DESC
        ) = 1
        ORDER BY set_number
    """)

    fallback = []
    for row in last_record:
        if row.rpe and row.rpe >= 9.5:
            suggested_weight = row.weight_kg  # 据え置き
            suggested_reps = row.reps + 1
        elif row.rpe and row.rpe <= 7.0:
            suggested_weight = row.weight_kg * 1.05  # 5%増
            suggested_reps = row.reps
        else:
            suggested_weight = row.weight_kg * 1.025  # 2.5%増
            suggested_reps = row.reps

        fallback.append({
            "set_number": row.set_number,
            "suggested_weight_kg": round(suggested_weight, 1),
            "suggested_reps": suggested_reps,
            "suggested_volume": round(suggested_weight * suggested_reps, 1)
        })

    return fallback, "fallback"

```

**Input画面のレイアウトイメージ：**

```
┌─────────────────────────────────────────────────────┐
│  📝 トレーニング入力                                  │
├─────────────────────────────────────────────────────┤
│                                                     │
│  日付: [2025/01/20      ▼]                          │
│  部位: [胸              ▼]                           │
│  種目: [ベンチプレス      ▼]                          │
│                                                     │
│  ┌─ 💡 今回の提案 ──────────────────────────────┐   │
│  │ セット  重量     回数    RPE                   │   │
│  │ 1      80.0kg   5      -                     │   │
│  │ 2      85.0kg   3      -                     │   │
│  │ 3      90.0kg   1      -                     │   │
│  │                                              │   │
│  │ 📊 提案通りの総負荷量: 745.0 kg               │   │
│  │    (前回総負荷量: 720.0 kg  +3.5%)            │   │
│  └──────────────────────────────────────────────┘   │
│                                                     │
│  ┌─ ⏱️ 休憩タイマー ───────────────────────────┐   │
│  │                                              │   │
│  │              ⏱️ 1:30                         │   │
│  │                                              │   │
│  │  [1分] [1分半] [2分] [3分] [カスタム: ___分]  │   │
│  │                                              │   │
│  │  [▶ スタート]  [⏹ リセット]                   │   │
│  │                                              │   │
│  │  ※ タイマー終了時にアラーム音 + 画面通知       │   │
│  └──────────────────────────────────────────────┘   │
│                                                     │
│  ┌─ ✏️ セット入力（自動保存）─────────────────── ┐   │
│  │ セット  重量(kg)  回数   RPE    メモ    状態   │   │
│  │ 1      [80.0  ]  [5  ]  [8.0]  [    ]  ✅   │   │
│  │ 2      [85.0  ]  [3  ]  [9.0]  [    ]  ✅   │   │
│  │ 3      [90.0  ]  [1  ]  [9.5]  [重い]  ✅   │   │
│  │ 4      [    ]    [   ]  [   ]  [    ]  ⬜   │   │
│  │                                               │   │
│  │ [＋ セット追加]  [🗑 最終セット削除]            │   │
│  │                                               │   │
│  │ ┌──────────────────────────────────────────┐ │   │
│  │ │ 📊 現在の総負荷量: 745.0 kg               │ │   │
│  │ │    前回総負荷量:   720.0 kg               │ │   │
│  │ │    差分:          +25.0 kg (+3.5%) ✅    │ │   │
│  │ └──────────────────────────────────────────┘ │   │
│  │                                               │   │
│  │ 💾 自動保存済み (最終保存: 15:32:10)           │   │
│  │ ⏰ 編集可能期限: 18:32:10                      │   │
│  └──────────────────────────────────────────────┘   │
│                                                     │
│  ┌─ 📋 直近3回の実績 ──────────────────────────┐    │
│  │                                              │    │
│  │ ■ 2025/1/17  総負荷量: 720.0 kg              │    │
│  │ セット  重量     回数   RPE                    │    │
│  │ 1      77.5kg   5     8.0                    │    │
│  │ 2      82.5kg   3     8.5                    │    │
│  │ 3      87.5kg   1     9.5                    │    │
│  │                                              │    │
│  │ ■ 2025/1/13  総負荷量: 695.0 kg              │    │
│  │ セット  重量     回数   RPE                    │    │
│  │ 1      77.5kg   5     7.5                    │    │
│  │ 2      82.5kg   3     8.5                    │    │
│  │ 3      85.0kg   1     9.0                    │    │
│  │                                              │    │
│  │ ■ 2025/1/10  総負荷量: 667.5 kg              │    │
│  │ セット  重量     回数   RPE                    │    │
│  │ 1      75.0kg   5     7.5                    │    │
│  │ 2      80.0kg   3     8.0                    │    │
│  │ 3      85.0kg   1     9.0                    │    │
│  └──────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```__

```

**自動保存のロジック：**

```
保存タイミング:
  フォーカスが外れた時（on_change イベント）に自動保存

保存条件:
  - 重量 > 0 かつ 回数 > 0 が入力されているセットのみ保存
  - RPE・メモは空でも保存される（後から追記可能）
  - 保存済みセットに ✅ マーク表示
  - 未保存セットは ⬜ マーク表示

保存方式:
  - 新規セット → BigQueryにINSERT
  - 既存セット → BigQueryにUPDATE（log_idで特定）
  - 最終保存時刻を画面に表示

```

**当日復元のロジック：**

```
種目選択時の動作:
  1. 選択した日付・種目で raw.training_log を検索
  2. 既存レコードがあれば:
     → セット入力欄に自動復元
     → 「⚠️ 本日のXXXの記録があります（編集可能）」を表示
     → 編集可能期限内であれば編集可能
     → 期限超過の場合は読み取り専用で表示
  3. 既存レコードがなければ:
     → 空のセット入力欄を表示
     → 提案値を表示

```

**編集制限のロジック：**

```
編集可能条件:
  CURRENT_TIMESTAMP() < created_at + INTERVAL 3 HOUR

判定タイミング:
  - 種目選択時に判定
  - 画面上に編集可能期限を表示（⏰ 編集可能期限: HH:MM:SS）
  - 期限超過後は入力フィールドをdisabled（グレーアウト）

カレンダーからの編集:
  - カレンダー画面で日付クリック → 詳細表示
  - 「編集」ボタン → Input画面に遷移（日付・種目がプリセットされた状態）
  - 3時間以内であれば編集可能、超過していればボタン非表示

```

### **2. カレンダー（Calendar）**

| **機能** | **詳細** |
| --- | --- |
| 月間カレンダー | トレーニングした日にマーク表示 |
| 部位表示 | マークされた日にその日の部位を表示（例: 胸の日） |
| 詳細表示 | 日付クリックでその日の種目・重量・回数・セットを表示 |
| 編集ボタン | 詳細表示内に「編集」ボタン。3時間以内なら Input 画面に遷移。 |
| 月切り替え | 前月・翌月への切り替え |
| ユーザー切り替え | 自分以外のユーザーのカレンダーも閲覧可能（編集不可） |
| データソース | `mart.m_calendar`, `mart.fct_training_set` |

**Calendar画面のレイアウトイメージ：**

```
┌─────────────────────────────────────────────────────┐
│  📅 カレンダー                                       │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ユーザー: [自分 ▼]                                  │
│  [◀ 前月]   2025年1月   [翌月 ▶]                    │
│                                                     │
│  月   火   水   木   金   土   日                    │
│            1    2    3    4    5                     │
│                      🟢脚                            │
│  6    7    8    9    10   11   12                    │
│  🟢胸                🟢背中                           │
│  13   14   15   16   17   18   19                   │
│  🟢肩                🟢胸                             │
│  20   21   22   23   24   25   26                   │
│  🟢脚                                               │
│  27   28   29   30   31                             │
│                                                     │
│  ┌─ 📋 1/20（月）の詳細 ──────────────────────┐    │
│  │ 部位: 脚                                    │    │
│  │ 総ボリューム: 12,745 kg                      │    │
│  │                                             │    │
│  │ ■ スクワット                                 │    │
│  │ セット  重量      回数   RPE                  │    │
│  │ 1      100.0kg   8     8.0                  │    │
│  │ 2      110.0kg   5     8.5                  │    │
│  │ 3      120.0kg   3     9.0                  │    │
│  │ 4      130.0kg   1     9.5                  │    │
│  │                                             │    │
│  │ ■ レッグプレス                                │    │
│  │ セット  重量      回数   RPE                  │    │
│  │ 1      150.0kg   12    7.5                  │    │
│  │ 2      160.0kg   10    8.0                  │    │
│  │ 3      170.0kg   8     8.5                  │    │
│  │                                             │    │
│  │ ■ レッグカール                                │    │
│  │ セット  重量      回数   RPE                  │    │
│  │ 1      40.0kg    15    7.0                  │    │
│  │ 2      45.0kg    12    8.0                  │    │
│  │ 3      45.0kg    10    8.5                  │    │
│  │                                             │    │
│  │ [✏️ 編集する]  ← 3時間以内のみ表示           │    │
│  └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘

```

**編集ボタンの動作：**

```
1. 「✏️ 編集する」クリック
2. Input画面に遷移
3. 日付・部位・種目がプリセットされた状態で表示
4. 既存のセットデータが復元される
5. 編集→自動保存

表示条件:
  - 自分の記録のみ表示（他ユーザーの記録には非表示）
  - created_at + 3時間以内の記録のみ表示
  - 期限超過の場合はボタン非表示

```

---

### **3. ダッシュボード（Dashboard）**

| **機能** | **詳細** |
| --- | --- |
| KPIカード | 主要複合種目ごとの週次変化率を表示（目標: ≧1.0%） |
| 進捗グラフ | 7日間移動平均ボリュームの推移（折れ線グラフ） |
| 種目別グラフ | 種目を選択してボリューム推移を表示 |
| 期間フィルタ | 表示期間の切り替え（1ヶ月/3ヶ月/6ヶ月/全期間） |
| ユーザー切り替え | 自分以外のユーザーのダッシュボードも閲覧可能 |
| データソース | `mart.m_progress_curve` |

**Dashboard画面のレイアウトイメージ：**

```
┌─────────────────────────────────────────────────────┐
│  📊 ダッシュボード                                    │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ユーザー: [自分 ▼]                                  │
│                                                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐│
│  │ベンチプレス│ │スクワット │ │ﾊｰﾌﾃﾞｯﾄﾞﾘﾌﾄ│ │  OHP   ││
│  │ +2.3% ✅ │ │ +1.1% ✅ │ │ -0.5% ❌ │ │+3.0% ✅││
│  └──────────┘ └──────────┘ └──────────┘ └────────┘│
│                                                     │
│  期間: [1ヶ月 ▼]                                     │
│                                                     │
│  📈 7日間移動平均ボリューム推移                        │
│  ┌─────────────────────────────────────────────┐   │
│  │     ╱─╲                                     │   │
│  │   ╱    ╲    ╱─────╲                         │   │
│  │ ╱       ╲╱          ╲╱─────                 │   │
│  │                                              │   │
│  │ 1/1  1/5  1/10  1/15  1/20                  │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  種目: [ベンチプレス ▼]                               │
│  ┌─────────────────────────────────────────────┐   │
│  │ （選択した種目のボリューム推移グラフ）          │   │
│  └─────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘

```

---

### **4. ランキング（Ranking）**

| **機能** | **詳細** |
| --- | --- |
| 総合ランキング | 週間/月間/全期間の全種目総ボリュームランキング |
| 部位別ランキング | 部位を選択して週間/月間/全期間のランキング表示 |
| 期間切り替え | タブで週間/月間/全期間を切り替え |
| 順位変動表示 | 前回からの順位変動を↑↓→で表示 |
| データソース | `mart.m_ranking_weekly`, `m_ranking_monthly`, `m_ranking_alltime`, `m_ranking_bodypart` |

**Ranking画面のレイアウトイメージ：**

```
┌─────────────────────────────────────────────────────┐
│  🏆 ランキング                                       │
├─────────────────────────────────────────────────────┤
│                                                     │
│  [週間] [月間] [全期間]                               │
│                                                     │
│  ── 総合ランキング（1/13〜1/19）──                    │
│  ┌─────────────────────────────────────────────┐   │
│  │ 🥇 ユーザーA: 25,000 kg  ↑ (前回2位)        │   │
│  │ 🥈 ユーザーB: 22,000 kg  ↓ (前回1位)        │   │
│  │ 🥉 ユーザーC: 18,000 kg  → (前回3位)        │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  ── 部位別ランキング ──                               │
│  部位: [胸 ▼]                                        │
│  ┌─────────────────────────────────────────────┐   │
│  │ 🥇 ユーザーB: 8,000 kg   ↑ (前回2位)        │   │
│  │ 🥈 ユーザーA: 7,500 kg   ↓ (前回1位)        │   │
│  │ 🥉 ユーザーC: 5,000 kg   → (前回3位)        │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
└─────────────────────────────────────────────────────┘

```

---

### **5. ソーシャル（Social）**

| **機能** | **詳細** |
| --- | --- |
| 記録更新フィード | 直近7日間の記録更新を時系列で表示 |
| 最高重量更新 | 🎉 ユーザーAがベンチプレスの最高重量を更新！80kg → 85kg |
| 最高ボリューム更新 | 💪 ユーザーBがスクワットの最高ボリュームを更新！2400 → 2700 |
| 他ユーザーの記録閲覧 | ユーザー・日付・部位で絞り込んで閲覧（編集不可） |
| データソース | `mart.m_personal_record`（is_new=TRUE）, `mart.fct_training_set` |

**Social画面のレイアウトイメージ：**

```
┌─────────────────────────────────────────────────────┐
│  👥 ソーシャル                                        │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ── 🔔 記録更新フィード ──                            │
│  ┌─────────────────────────────────────────────┐   │
│  │ 🎉 1/20 ユーザーAがベンチプレスの              │   │
│  │    最高重量を更新！ 80kg → 85kg               │   │
│  │                                              │   │
│  │ 💪 1/19 ユーザーBがスクワットの                │   │
│  │    最高ボリュームを更新！ 2,400 → 2,700       │   │
│  │                                              │   │
│  │ 🎉 1/18 ユーザーCがハーフデッドリフトの        │   │
│  │    最高重量を更新！ 120kg → 130kg             │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  ── 👤 他ユーザーの記録 ──                            │
│  ユーザー: [ユーザーA ▼]                              │
│  日付:     [2025/01/20 ▼]                            │
│  部位:     [全部位     ▼]                             │
│  ┌─────────────────────────────────────────────┐   │
│  │ ■ ベンチプレス（胸）                          │   │
│  │ セット  重量      回数   RPE                   │   │
│  │ 1      80.0kg    5     8.0                   │   │
│  │ 2      85.0kg    3     9.0                   │   │
│  │ 3      90.0kg    1     9.5                   │   │
│  │                                              │   │
│  │ ■ インクラインDBプレス（胸）                    │   │
│  │ セット  重量      回数   RPE                   │   │
│  │ 1      30.0kg    10    7.5                   │   │
│  │ 2      32.5kg    8     8.0                   │   │
│  │ 3      32.5kg    7     8.5                   │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
└─────────────────────────────────────────────────────┘

```

---

### **6. 種目追加リクエスト（ExerciseRequest）**

| **機能** | **詳細** |
| --- | --- |
| リクエスト送信 | 種目名・部位・追加理由を入力して送信 |
| リクエスト状況 | 自分のリクエストのステータス確認（pending/approved/rejected） |
| データソース | `raw.exercise_request` |

**ExerciseRequest画面のレイアウトイメージ：**

```
┌─────────────────────────────────────────────────────┐
│  ➕ 種目追加リクエスト                                 │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ── 新規リクエスト ──                                 │
│  種目名: [ディップス        ]                         │
│  部位:   [胸              ▼]                         │
│  理由:   [大胸筋下部を鍛えたい ]                      │
│                                                     │
│  [📤 リクエスト送信]                                  │
│                                                     │
│  ── 📋 リクエスト履歴 ──                              │
│  ┌─────────────────────────────────────────────┐   │
│  │ 日付       種目名       部位  ステータス      │   │
│  │ 2025/1/20  ディップス    胸   ⏳ 承認待ち     │   │
│  │ 2025/1/10  ケーブルカール 腕   ✅ 承認済み     │   │
│  │ 2025/1/05  懸垂         背中  ❌ 却下         │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
└─────────────────────────────────────────────────────┘

```

---

### **7. 管理者画面（Admin）**

| **機能** | **詳細** |
| --- | --- |
| アクセス制御 | `is_admin=TRUE` のユーザーのみ表示 |
| 種目承認/却下 | pending状態のリクエスト一覧を表示し、承認または却下 |
| 種目マスタ管理 | 種目の追加・編集・無効化（CRUD） |
| 承認時の動作 | `raw.exercise_master` に新種目を追加、`raw.exercise_request` のstatusを更新 |
| データソース | `raw.exercise_request`, `raw.exercise_master` |

**Admin画面のレイアウトイメージ：**

```
┌─────────────────────────────────────────────────────┐
│  ⚙️ 管理者画面                                       │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ── 📬 承認待ちリクエスト ──                          │
│  ┌─────────────────────────────────────────────┐   │
│  │ 日付       ユーザー   種目名     部位  理由   │   │
│  │ 2025/1/20  ユーザーA  ディップス  胸   大胸筋 │   │
│  │            [✅ 承認] [❌ 却下]               │   │
│  │                                              │   │
│  │ 2025/1/19  ユーザーB  シュラッグ  肩   僧帽筋 │   │
│  │            [✅ 承認] [❌ 却下]               │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  ── 承認時の追加設定 ──                               │
│  （承認ボタン押下後に表示）                            │
│  ┌─────────────────────────────────────────────┐   │
│  │ 種目ID:     [dips           ] (自動生成)     │   │
│  │ 種目名:     [ディップス      ] (リクエスト値)  │   │
│  │ 部位:       [胸             ▼]               │   │
│  │ 複合種目:   [☐] (KPI対象にするか)             │   │
│  │ 表示順:     [4              ]                │   │
│  │                                              │   │
│  │ [💾 承認して追加]                              │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  ── 📋 種目マスタ管理 ──                              │
│  部位フィルタ: [全部位 ▼]                             │
│  ┌─────────────────────────────────────────────┐   │
│  │ ID              種目名           部位  複合  │   │
│  │ bench_press     ベンチプレス      胸    ✅   │   │
│  │ incline_db      インクラインDB    胸    ☐   │   │
│  │ cable_fly       ケーブルフライ    胸    ☐   │   │
│  │ dips            ディップス        胸    ☐   │   │
│  │ ...                                         │   │
│  │                                              │   │
│  │ [✏️ 編集] [🚫 無効化]  ← 各行に表示          │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  ── ➕ 種目の手動追加 ──                              │
│  種目ID:   [              ]                         │
│  種目名:   [              ]                         │
│  部位:     [             ▼]                         │
│  複合種目: [☐]                                      │
│  表示順:   [              ]                         │
│                                                     │
│  [💾 追加]                                           │
│                                                     │
└─────────────────────────────────────────────────────┘

```

**承認フローの詳細：**

```
1. ユーザーが ExerciseRequest 画面からリクエスト送信
   → raw.exercise_request に status='pending' で INSERT

2. 管理者が Admin 画面で承認待ちリクエストを確認

3-a. 承認の場合:
   → 承認時の追加設定フォームが表示
   → 種目ID・複合種目フラグ・表示順を設定
   → 「承認して追加」クリック
   → raw.exercise_master に新種目を INSERT
   → raw.exercise_request の status='approved', reviewed_by, reviewed_at を UPDATE
   → 次回 dbt run で mart.d_exercise に反映

3-b. 却下の場合:
   → raw.exercise_request の status='rejected', reviewed_by, reviewed_at を UPDATE

```

---

### **6.3. 認証設計**

```
認証方式: Streamlit のパスワード認証

ログインフロー:
1. ユーザーがアプリにアクセス
2. ユーザー名とパスワードの入力画面を表示
3. 認証成功 → セッションに user_id, user_name, is_admin を保持
4. is_admin=TRUE → サイドバーに管理者画面が表示される
5. is_admin=FALSE → 管理者画面は非表示

パスワード管理:
- Streamlit Cloud の secrets.toml に格納
- ユーザーごとに個別パスワード（ハッシュ化）

secrets.toml の例:
[passwords]
user_001 = "hashed_password_1"
user_002 = "hashed_password_2"
user_003 = "hashed_password_3"

[users]
user_001 = {name = "ユーザー1", is_admin = true}
user_002 = {name = "ユーザー2", is_admin = false}
user_003 = {name = "ユーザー3", is_admin = false}

```

---

# **7. 通知設計**

### **7.1. 通知一覧と負荷試算**

| **通知種別** | **判定ロジック** | **トリガー** | **月間通知数（3ユーザー）** |
| --- | --- | --- | --- |
| 筋トレ開始通知 | その日初回のトレーニング記録登録時 | 記録登録時（自動） | 約60通（3ユーザー×20日） |
| 3日未実施リマインド | `m_last_training.needs_3day_reminder = TRUE` | Cloud Scheduler 日次 07:00 JST | 最大30通 |
| 7日空き（部位別） | `m_last_training.needs_7day_reminder = TRUE`（「その他」除外） | Cloud Scheduler 日次 07:00 JST | 最大36通 |
| 週間ランキング | `m_ranking_weekly` の最新週データ | Cloud Scheduler 毎週月曜 08:00 JST | 12通 |
| 月間ランキング | `m_ranking_monthly` の最新月データ | Cloud Scheduler 毎月1日 08:00 JST | 3通 |
| **合計** |  |  | **最大141通/月（無料枠200通内）** |

### **7.2. 無料枠対策**

```
通知数: 最大141通/月（無料枠200通に対して余裕30%）

追加の安全策:
1. 3日未実施と7日空き通知の重複排除
   → 同日に両方該当する場合は1通にまとめる

2. 通知カウンター実装
   → 月間送信数をBigQueryで管理
   → 残数20通以下で低優先度通知を抑制

優先度:
  高: 筋トレ開始通知（自動・ユーザー体験に直結）
  高: ランキング通知（モチベーション維持に重要）
  中: 3日未実施リマインド
  低: 7日空き（部位別）← 残数少ない時に抑制

```

### **7.3. LINE通知メッセージ**

```
【筋トレ開始通知】（その日初回の記録登録時に自動送信）
🏋️ ユーザーAがトレーニングを開始しました！
今日のメニュー: 胸の日

📱 アプリを開く: https://your-app.streamlit.app

---

【3日未実施リマインド】
⚠️ 3日間トレーニングしていません！
最後のトレーニング: 2025/01/15（胸の日）

💪 今日もトレーニングしましょう！
📱 アプリを開く: https://your-app.streamlit.app

---

【7日空きリマインド（部位別）】※「その他」は対象外
⚠️ 「脚」のトレーニングが7日以上空いています！
最後の脚トレ: 2025/01/10

📱 アプリを開く: https://your-app.streamlit.app

---

【週間ランキング通知】
🏆 週間ランキング（1/13〜1/19）

🥇 ユーザーA: 25,000 kg  ↑ (前回2位)
🥈 ユーザーB: 22,000 kg  ↓ (前回1位)
🥉 ユーザーC: 18,000 kg  → (前回3位)

📱 詳細を見る: https://your-app.streamlit.app

---

【月間ランキング通知】
🏆 月間ランキング（2025年1月）

🥇 ユーザーA: 100,000 kg  ↑ (前回2位)
🥈 ユーザーB: 88,000 kg   ↓ (前回1位)
🥉 ユーザーC: 72,000 kg   → (前回3位)

📱 詳細を見る: https://your-app.streamlit.app

```

**変動表示のルール：**

| **表示** | **条件** |
| --- | --- |
| ↑ | 前回より順位が上がった |
| ↓ | 前回より順位が下がった |
| → | 前回と同じ順位 |
| NEW | 前回データなし（初参加） |

### **7.4. Cloud Scheduler ジョブ設定**

```
Cloud Scheduler 無料枠: 3ジョブまで
必要ジョブ: 4つ → 統合して3ジョブに収める

統合版（3ジョブ）:
1. daily-pipeline     : 毎日 06:00 JST
   → dbt run + dbt test + 日次通知判定・送信
                  + 週次判定でBigQuery MLモデル再学習

2. weekly-ranking     : 毎週月曜 08:00 JST
   → 週間ランキング通知送信

3. monthly-ranking    : 毎月1日 08:00 JST
   → 月間ランキング通知送信

```

| ジョブ名 | cron式 | 対象Cloud Function | 内容 |
| --- | --- | --- | --- |
| `daily-pipeline` | `0 6 * * *` | `dbt-runner` → `notifier` | dbt run + dbt test + 週1回MLモデル再学習（月曜のみ） + 日次通知 |
| `weekly-ranking` | `0 8 * * 1` | `notifier` | 週間ランキング通知 |
| `monthly-ranking` | `0 8 1 * *` | `notifier` | 月間ランキング通知 |

**MLモデル再学習の判定ロジック（Cloud Functions内）：**

```jsx
# cloud_functions/dbt_runner/main.py の一部（疑似コード）

from datetime import datetime

def run_daily_pipeline():
    # 1. dbt run（毎日実行）
    run_dbt("run")

    # 2. dbt test（毎日実行）
    run_dbt("test")

    # 3. BigQuery MLモデル再学習（月曜のみ）
    today = datetime.now().weekday()  # 0=月曜
    if today == 0:
        retrain_ml_model()

    # 4. 日次通知判定・送信
    send_daily_notifications()

def retrain_ml_model():
    """BigQuery MLモデルを再学習"""
    query = """
        CREATE OR REPLACE MODEL mart.training_predictor
        OPTIONS(
            model_type = 'BOOSTED_TREE_REGRESSOR',
            input_label_cols = ['next_weight_kg'],
            num_trials = 5,
            max_iterations = 50,
            early_stop = TRUE
        ) AS
        -- （学習クエリは設計書5.3参照）
    """
    bigquery_client.query(query).result()

    # 再学習後にm_ml_suggestionを更新
    run_dbt("run", select="m_ml_suggestion")

```

---

# **8. セキュリティと運用**

### **8.1. 認証情報管理**

| **情報** | **格納場所** | **アクセス元** |
| --- | --- | --- |
| LINE Channel Access Token | GCP Secret Manager | Cloud Functions (sa-cf-notifier) |
| LINE Channel Secret | GCP Secret Manager | Cloud Functions (sa-cf-notifier) |
| BigQuery SA Key (Streamlit用) | Streamlit Cloud secrets.toml | Streamlit Cloud |
| BigQuery SA Key (dbt用) | ローカル secrets/ | Cloud Functions (sa-dbt-runner) |
| アプリパスワード（ハッシュ） | Streamlit Cloud secrets.toml | Streamlit Cloud |
| ユーザー情報（is_admin等） | Streamlit Cloud secrets.toml | Streamlit Cloud |

### **8.2. 権限管理（最小権限の原則）**

| **アカウント** | **用途** | **BigQuery** | **Secret Manager** |
| --- | --- | --- | --- |
| `sa-dbt-runner` | データ変換 | `dataEditor` + `jobUser` | なし |
| `sa-cf-notifier` | LINE通知 | `dataViewer` + `jobUser` | `secretAccessor` |
| `sa-streamlit-app` | 入力UI・可視化 | `dataEditor` + `jobUser` | なし |

### **8.3. アプリケーションレベルの権限**

| **ユーザー種別** | **閲覧** | **入力** | **編集** | **種目リクエスト** | **種目承認** | **マスタ管理** |
| --- | --- | --- | --- | --- | --- | --- |
| 一般ユーザー | ✅ 全員分 | ✅ 自分のみ | ✅ 自分のみ（3時間以内） | ✅ | ❌ | ❌ |
| 管理者 | ✅ 全員分 | ✅ 自分のみ | ✅ 自分のみ（3時間以内） | ✅ | ✅ | ✅ |

### **8.4. データ保護**

```
暗号化:
  - BigQuery: Google管理の暗号化キーによるデフォルト暗号化（保存時）
  - 通信: HTTPS（Streamlit Cloud / Cloud Functions ともにデフォルト）

バックアップ:
  - BigQuery: raw層のデータは変更・削除しない（追記のみ + 論理削除）
  - 論理削除: is_deleted フラグで管理。物理削除は行わない
  - テーブルスナップショット: 月次でBigQueryのスナップショットを取得

個人情報:
  - 体重データ等は個人情報に該当しうる
  - リポジトリはプライベート設定
  - アクセスはパスワード認証で制限

```

### **8.5. コスト監視**

| **サービス** | **無料枠** | **監視方法** |
| --- | --- | --- |
| BigQuery | 10GB Storage / 1TB Query/月 | GCP予算アラート（$0設定済み） |
| Cloud Functions | 200万回/月 | GCPコンソールで確認 |
| Cloud Scheduler | 3ジョブ | 3ジョブに統合済み |
| LINE Messaging API | 200通/月 | 通知カウンターをBigQueryで管理 |
| Streamlit Cloud | 1アプリ | 1アプリのみ使用 |
| Secret Manager | 6アクティブバージョン | 2シークレットのみ使用 |

---

# **9. エラーハンドリングと監視**

### **9.1. エラーハンドリング戦略**

| **コンポーネント** | **エラー種別** | **対応** |
| --- | --- | --- |
| Streamlit → BigQuery書き込み | 接続エラー / タイムアウト | 3回リトライ。失敗時はユーザーにエラーメッセージ表示。 |
| Streamlit → BigQuery書き込み | バリデーションエラー | 画面上に具体的なエラー内容を表示。保存しない。 |
| Streamlit 自動保存 | 保存失敗 | セット行の状態を ⚠️ に変更。リトライボタン表示。 |
| dbt run | モデルコンパイルエラー | Cloud Functions のログに記録。次回日次バッチで再実行。 |
| dbt test | テスト失敗 | ログに記録。パイプラインは停止しない（警告扱い）。 |
| Cloud Functions → LINE | API エラー / レート制限 | 3回リトライ（指数バックオフ）。失敗時はログに記録。 |
| Cloud Functions → LINE | 無料枠超過 | 通知カウンターで事前検知。低優先度通知を抑制。 |
| Cloud Scheduler | ジョブ実行失敗 | GCPが自動リトライ（最大5回）。 |

### **9.2. ログ管理**

```
ログの保存先:
  - Cloud Functions → Cloud Logging（GCPデフォルト）
  - dbt → Cloud Functions 経由で Cloud Logging
  - Streamlit → Streamlit Cloud のログ

ログに含める情報:
  - タイムスタンプ（JST）
  - 処理名（dbt run / notification / save_record 等）
  - 成功/失敗
  - エラー時: エラーメッセージ + スタックトレース
  - 通知時: 送信先ユーザー + 通知種別 + 月間送信数

```

### **9.3. 通知カウンター（LINE無料枠管理）**

```sql
-- raw.notification_log（通知送信ログ）
CREATE TABLE IF NOT EXISTS raw.notification_log (
    notification_id   STRING      NOT NULL,   -- UUID
    user_id           STRING      NOT NULL,   -- 送信先ユーザー
    notification_type STRING      NOT NULL,   -- start/3day/7day/weekly_ranking/monthly_ranking
    status            STRING      NOT NULL,   -- sent/failed/suppressed
    sent_at           TIMESTAMP   NOT NULL
)
OPTIONS (
    description = '通知送信ログ。LINE無料枠の管理に使用。'
);

```

```sql
-- 月間送信数の確認クエリ（Cloud Functions内で使用）
SELECT COUNT(*) AS monthly_count
FROM raw.notification_log
WHERE status = 'sent'
  AND sent_at >= TIMESTAMP_TRUNC(CURRENT_TIMESTAMP(), MONTH, 'Asia/Tokyo')

```

```
通知抑制ロジック:
  monthly_count >= 180 → 低優先度（7日空き）を抑制
  monthly_count >= 190 → 中優先度（3日未実施）も抑制
  monthly_count >= 200 → 全通知を停止（開始通知・ランキングも）

```

---

# **10. 非機能要件**

| **項目** | **要件** |
| --- | --- |
| 可用性 | 99%（月間7.2時間のダウンタイム許容）。Streamlit Cloudのスリープ（30分未使用）は許容。 |
| レイテンシ | Streamlit入力→BigQuery反映: 5秒以内。自動保存: 3秒以内。 |
| データ保持期間 | raw層: 無期限。mart層: 無期限（データ量が少ないため）。 |
| 同時接続数 | 最大3ユーザー |
| RPO（目標復旧時点） | 24時間（日次バッチで復旧可能） |
| RTO（目標復旧時間） | 4時間 |
| 編集可能期間 | レコード作成から3時間以内 |

---

# **11. テスト戦略**

### **11.1. テスト種別**

| **テスト種別** | **対象** | **ツール** | **実行タイミング** |
| --- | --- | --- | --- |
| スキーマテスト | dbtモデル（unique, not_null, accepted_values） | dbt test | CI（PR時）+ 日次バッチ |
| ユニットテスト | Streamlit utils（バリデーション、認証） | pytest | CI（PR時） |
| ユニットテスト | Cloud Functions（通知判定、カウンター） | pytest | CI（PR時） |
| 統合テスト | パイプライン全体（E2E） | 手動 | 各Phase完了時 |
| セキュリティスキャン | コード内の認証情報漏洩 | gitleaks | CI（PR時） |

### **11.2. dbt テスト一覧**

| **モデル** | **テスト** | **目的** |
| --- | --- | --- |
| `stg_training_log.log_id` | unique, not_null | 主キーの一意性 |
| `stg_training_log.weight_kg` | not_null | 必須項目 |
| `stg_training_log.reps` | not_null | 必須項目 |
| `stg_training_log.volume` | not_null | 計算列の整合性 |
| `fct_training_set.log_id` | unique, not_null | 主キーの一意性 |
| `d_exercise.exercise_id` | unique, not_null | マスタの一意性 |
| `d_exercise.body_part_id` | accepted_values | 定義済み部位のみ |
| `d_body_part.body_part_id` | unique, not_null | マスタの一意性 |
| `d_user.user_id` | unique, not_null | マスタの一意性 |
| `m_ranking_*.rank` | not_null | ランキング計算の整合性 |
| `m_personal_record.record_type` | accepted_values | max_weight/max_volume のみ |
| `m_calendar.training_date` | not_null | 日付の存在*_ |
| `m_last_training.user_id` | not_null | ユーザーの存*_ |

---

# **12. デプロイ戦略**

### **12.1. CI/CDパイプライン**

```
PR作成時（CI）:
  1. Lint & Format チェック（ruff, black）
  2. dbt compile + dbt test
  3. pytest（ユニットテスト）
  4. gitleaks（セキュリティスキャン）
  → 全て通過でマージ可能

mainマージ時（CD）:
  1. GCPにWorkload Identity Federationで認証
  2. Cloud Functions（dbt-runner）をデプロイ
  3. Cloud Functions（notifier）をデプロイ

Streamlit:
  → Streamlit CloudがGitHubリポジトリを監視
  → mainブランチの変更を自動検知してデプロイ

```

### **12.2. ブランチ戦略**

```
main      → 本番環境。常に動く状態を保つ。
develop   → 開発統合。テスト通過後にmainへマージ。
feature/* → 各機能開発。developから分岐→developへマージ。
docs/*    → ドキュメント変更。developから分岐→developへマージ。
fix/*     → バグ修正。developから分岐→developへマージ。
hotfix/*  → 緊急修正。mainから分岐→mainへマージ→developにも反映。

```

---

# **13. 運用手順**

### **13.1. 日次運用（自動）**

```
06:00 JST - daily-pipeline ジョブ実行
  1. Cloud Functions (dbt-runner) 起動
  2. dbt run（staging → mart 変換）
  3. dbt test（スキーマテスト）
  4. Cloud Functions (notifier) 起動
  5. m_last_training を参照して通知判定
  6. 該当ユーザーにLINE通知送信
  7. notification_log に記録

```

### **13.2. 週次運用（自動）**

```
毎週月曜 08:00 JST - weekly-ranking ジョブ実行
  1. Cloud Functions (notifier) 起動
  2. m_ranking_weekly の最新週データを取得
  3. 前週との順位変動を計算
  4. 全ユーザーにLINE通知送信
  5. notification_log に記録

```

### **13.3. 月次運用（自動）**

```
毎月1日 08:00 JST - monthly-ranking ジョブ実行
  1. Cloud Functions (notifier) 起動
  2. m_ranking_monthly の最新月データを取得
  3. 前月との順位変動を計算
  4. 全ユーザーにLINE通知送信
  5. notification_log に記録

```

### **13.4. 障害時の対応フロー**

```
1. GCP予算アラート or Cloud Logging でエラーを検知

2. エラー種別を特定:
   a) dbt実行エラー → Cloud Logging でSQLエラーを確認 → モデル修正 → 手動再実行
   b) LINE通知エラー → Secret Manager のトークン有効期限を確認 → 再発行
   c) BigQuery接続エラー → サービスアカウントキーの有効性を確認
   d) Streamlit停止 → Streamlit Cloud のダッシュボードで状態確認 → 再起動

3. 修正後:
   → feature/fix ブランチで修正
   → PR → CI通過 → develop → main にマージ
   → 自動デプロイ

```

### **13.5. ユーザー追加手順**

```
1. raw.user_master にユーザーを追加（BigQueryコンソール or スクリプト）
   INSERT INTO raw.user_master VALUES
     ('user_004', '新ユーザー', 'U_LINE_ID_004', FALSE, TRUE, CURRENT_TIMESTAMP());

2. Streamlit Cloud の secrets.toml にパスワードを追加
   [passwords]
   user_004 = "hashed_password_4"
   [users]
   user_004 = {name = "新ユーザー", is_admin = false}

3. LINE公式アカウントを友だち追加してもらう

4. LINE user_id を取得して raw.user_master を更新
   UPDATE raw.user_master
   SET line_user_id = '実際のLINE_USER_ID'
   WHERE user_id = 'user_004';

5. dbt run を実行して mart.d_user に反映

6. 通知テスト
   → Cloud Functions を手動実行してLINE通知が届くか確認

```

### **13.6. 種目マスタ更新手順（管理者画面以外）**

```
緊急時やバッチでの一括追加の場合:

1. raw.exercise_master にINSERT
   INSERT INTO raw.exercise_master VALUES
     ('dips', 'ディップス', 'chest', FALSE, TRUE, 4, CURRENT_TIMESTAMP());

2. dbt run を実行して mart.d_exercise に反映

3. Streamlit アプリで種目が選択可能になったことを確認

```

---

# **14. 将来の拡張計画**

### **14.1. Phase 2: データ品質（Great Expectations）**

```
導入目的:
  dbt tests では対応しきれない高度なデータ品質テストを実施

追加テスト例:
  - m_progress_curve: ボリュームが現実的な範囲内か（0〜100,000）
  - m_ranking_*: ランキングに全ユーザーが含まれているか
  - fct_training_set: 1日あたりのセット数が異常でないか（100セット以上は異常）
  - raw.training_log: データ鮮度（24時間以内にデータが入っているか）

実行方式:
  dbt test の後に Great Expectations を実行
  テスト失敗時はログに記録（パイプラインは停止しない）

```

### **14.2. Phase 3: 自動化（Prefect Cloud）**

```
導入目的:
  Cloud Scheduler + Cloud Functions の組み合わせを
  Prefect Cloud に統合してワークフロー管理を一元化

置換対象:
  Cloud Scheduler → Prefect のスケジューラ
  Cloud Functions（dbt-runner）→ Prefect Flow

メリット:
  - ワークフローの可視化（DAG表示）
  - 実行履歴の管理
  - エラー時の自動リトライ設定
  - Slack/メール通知の統合

構成:
  Prefect Cloud（無料枠）
    └── Flow: daily-pipeline
        ├── Task: dbt run
        ├── Task: dbt test
        ├── Task: Great Expectations
        └── Task: LINE通知判定・送信

```

### **14.3. Phase 4: IaC（Terraform）**

```
導入目的:
  手動で構築したGCPインフラをコード化し、再現性を保証

管理対象:
  - BigQuery データセット・テーブル
  - Cloud Functions（デプロイ設定）
  - Cloud Scheduler（ジョブ設定）
  - Secret Manager（シークレット定義）
  - IAM（サービスアカウント・権限）
  - 予算アラート

ディレクトリ構成:
  terraform/
  ├── main.tf           # プロバイダー設定
  ├── bigquery.tf       # BigQuery リソース
  ├── cloud_functions.tf # Cloud Functions
  ├── scheduler.tf      # Cloud Scheduler
  ├── secrets.tf        # Secret Manager
  ├── iam.tf            # サービスアカウント・権限
  ├── variables.tf      # 変数定義
  ├── outputs.tf        # 出力定義
  └── terraform.tfvars  # 変数値（※.gitignore対象）

```

### 14.4. 補助ツール: Google Colab（任意）

```
用途:
  - 探索的データ分析（EDA）
  - BigQuery MLでは対応できない高度なモデルの実験
  - モデルの比較検証（BigQuery ML vs scikit-learn等）

位置づけ:
  - 本番のML提案はBigQuery MLで完結
  - Colabはあくまで実験・分析用の補助ツール
  - 必須ではない（なくても運用に支障なし）

利用方法:
  1. Google ColabからBigQueryに接続（同一Googleアカウント）
  2. mart.fct_training_set を読み込んで分析
  3. 結果をBigQuery MLのモデル改善に反映

```

---

# **15. 初期データ（種目マスタ修正版）**

```sql
-- デッドリフト → ハーフデッドリフトに変更
-- 「その他」部位を追加

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

```

**KPI対象種目（is_compound = TRUE）：**

| **種目** | **部位** |
| --- | --- |
| ベンチプレス | 胸 |
| ハーフデッドリフト | 背中 |
| オーバーヘッドプレス | 肩 |
| スクワット | 脚 |

---

# **16. 設計書変更履歴**
| **バージョン** | **日付** | **変更内容** |
| --- | --- | --- |
| v1.0 | - | 初版作成 |
| v2.0 | - | MVP再設計。フェーズ分割。テーブルスキーマ詳細化。 |
| v2.1 | 2026/03/05 | 新機能追加: カレンダー、ランキング（総合・部位別・変動表示）、ソーシャル（記録更新フィード・他ユーザー閲覧）、種目追加リクエスト/承認フロー、セット単位入力、自動保存、編集機能（3時間制限）、休憩タイマー、LINE通知改善（開始通知自動化・ランキング変動表示・アプリURLリンク）、通知カウンター、「その他」部位追加、デッドリフト→ハーフデッドリフト変更、Phase 5 ML提案計画追加。 |
| v2.2 | 2026/03/06 | BigQuery MLをPhase 1に統合（Phase 5削除）。データ品質ツールをGreat Expectations → dbt-expectations + Elementaryに変更。開発リソース比較検討書に基づく技術選定の反映。 |
