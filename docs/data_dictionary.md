# ============================================================
# データ定義書を作成（Part 1: Raw層まで）
# ============================================================

cat << 'DOCEOF' > docs/data_dictionary.md
# データ定義書

## 目次
1. [全体構成](#1-全体構成)
2. [Raw層](#2-raw層)
3. [Staging層](#3-staging層)
4. [Mart層 - ディメンション](#4-mart層---ディメンション)
5. [Mart層 - ファクト](#5-mart層---ファクト)
6. [Mart層 - メトリクス](#6-mart層---メトリクス)
7. [Mart層 - ML](#7-mart層---ml)

---

## 1. 全体構成

### レイクハウス3層構造

| レイヤー | データセット | 役割 | 書き込み元 |
|---|---|---|---|
| Raw | raw | 生データ格納。変換前の状態を保持。 | Streamlit |
| Staging | staging | クレンジング・型変換・重複排除。 | dbt |
| Mart | mart | 分析・アプリ参照用の最終データ。 | dbt |

### テーブル一覧

| レイヤー | テーブル名 | 種別 | 概要 |
|---|---|---|---|
| Raw | raw.training_log | トランザクション | トレーニング記録（1セット=1レコード） |
| Raw | raw.exercise_master | マスタ | 種目マスタ |
| Raw | raw.user_master | マスタ | ユーザーマスタ |
| Raw | raw.exercise_request | トランザクション | 種目追加リクエスト |
| Raw | raw.notification_log | ログ | 通知送信ログ |
| Staging | staging.stg_training_log | 変換 | クレンジング済みトレーニングログ |
| Mart | mart.d_body_part | ディメンション | 部位マスタ（6部位） |
| Mart | mart.d_exercise | ディメンション | 種目マスタ（有効のみ） |
| Mart | mart.d_user | ディメンション | ユーザーマスタ（有効のみ） |
| Mart | mart.fct_training_set | ファクト | トレーニング記録（ディメンション結合済み） |
| Mart | mart.m_progress_curve | メトリクス | 7日間移動平均・週次変化率（KPI） |
| Mart | mart.m_last_training | メトリクス | 最終トレーニング日・通知フラグ |
| Mart | mart.m_ranking_weekly | メトリクス | 週間ボリュームランキング |
| Mart | mart.m_ranking_monthly | メトリクス | 月間ボリュームランキング |
| Mart | mart.m_ranking_alltime | メトリクス | 全期間ボリュームランキング |
| Mart | mart.m_ranking_bodypart | メトリクス | 部位別ランキング |
| Mart | mart.m_personal_record | メトリクス | 個人記録・更新フラグ |
| Mart | mart.m_calendar | メトリクス | カレンダー表示用（日別サマリー） |
| Mart | mart.m_ml_suggestion | ML | BigQuery ML予測結果 |
| Mart | mart.training_predictor | MLモデル | BigQuery MLモデル定義 |

---

## 2. Raw層

### 2.1. raw.training_log

トレーニング記録。Streamlitから1セットごとに書き込まれる。

| No | カラム名 | 型 | NULL | デフォルト | 説明 |
|---|---|---|---|---|---|
| 1 | log_id | STRING | NOT NULL | - | 主キー。UUID v4。セットごとに一意。 |
| 2 | user_id | STRING | NOT NULL | - | ユーザーID。FK → user_master。 |
| 3 | exercise_name | STRING | NOT NULL | - | 種目名。セレクトボックスから選択。 |
| 4 | body_part | STRING | NOT NULL | - | 部位名。 |
| 5 | training_date | DATE | NOT NULL | - | トレーニング実施日。 |
| 6 | set_number | INT64 | NOT NULL | - | セット番号（1, 2, 3...）。 |
| 7 | weight_kg | FLOAT64 | NOT NULL | - | そのセットの使用重量 (kg)。 |
| 8 | reps | INT64 | NOT NULL | - | そのセットのレップ数。 |
| 9 | rpe | FLOAT64 | NULL可 | - | 主観的運動強度 (6.0-10.0)。 |
| 10 | memo | STRING | NULL可 | - | そのセットのメモ。 |
| 11 | input_source | STRING | NOT NULL | - | 入力元（streamlit）。 |
| 12 | created_at | TIMESTAMP | NOT NULL | - | 初回作成日時（UTC）。 |
| 13 | updated_at | TIMESTAMP | NOT NULL | - | 最終更新日時（UTC）。 |
| 14 | is_deleted | BOOL | NOT NULL | FALSE | 論理削除フラグ。 |

- パーティション: training_date（DAY）
- 主キー: log_id

データ例:

| log_id | user_id | exercise_name | set_number | weight_kg | reps | rpe |
|---|---|---|---|---|---|---|
| uuid-001 | user_001 | ベンチプレス | 1 | 80.0 | 5 | 8.0 |
| uuid-002 | user_001 | ベンチプレス | 2 | 85.0 | 3 | 9.0 |
| uuid-003 | user_001 | ベンチプレス | 3 | 90.0 | 1 | 9.5 |

### 2.2. raw.exercise_master

種目マスタ。Streamlitの管理者画面から書き込まれる。

| No | カラム名 | 型 | NULL | デフォルト | 説明 |
|---|---|---|---|---|---|
| 1 | exercise_id | STRING | NOT NULL | - | 主キー。例: bench_press。 |
| 2 | exercise_name | STRING | NOT NULL | - | 種目名。例: ベンチプレス。 |
| 3 | body_part_id | STRING | NOT NULL | - | 部位ID。FK → d_body_part。 |
| 4 | is_compound | BOOL | NOT NULL | - | 複合種目フラグ（KPI対象）。 |
| 5 | is_active | BOOL | NOT NULL | - | 有効フラグ。 |
| 6 | display_order | INT64 | NOT NULL | - | 表示順。 |
| 7 | updated_at | TIMESTAMP | NOT NULL | - | 更新日時。 |

- 主キー: exercise_id

### 2.3. raw.user_master

ユーザーマスタ。初期セットアップ時に手動投入。

| No | カラム名 | 型 | NULL | デフォルト | 説明 |
|---|---|---|---|---|---|
| 1 | user_id | STRING | NOT NULL | - | 主キー。例: user_001。 |
| 2 | user_name | STRING | NOT NULL | - | 表示名。 |
| 3 | line_user_id | STRING | NOT NULL | - | LINE Messaging API の userId。 |
| 4 | is_admin | BOOL | NOT NULL | - | 管理者フラグ（種目承認権限）。 |
| 5 | is_active | BOOL | NOT NULL | - | 有効フラグ。 |
| 6 | created_at | TIMESTAMP | NOT NULL | - | 作成日時。 |

- 主キー: user_id

### 2.4. raw.exercise_request

種目追加リクエスト。Streamlitから全ユーザーが送信可能。

| No | カラム名 | 型 | NULL | デフォルト | 説明 |
|---|---|---|---|---|---|
| 1 | request_id | STRING | NOT NULL | - | 主キー。UUID v4。 |
| 2 | user_id | STRING | NOT NULL | - | リクエストしたユーザー。 |
| 3 | exercise_name | STRING | NOT NULL | - | 提案する種目名。 |
| 4 | body_part_id | STRING | NOT NULL | - | 部位。 |
| 5 | reason | STRING | NULL可 | - | 追加理由。 |
| 6 | status | STRING | NOT NULL | - | pending / approved / rejected。 |
| 7 | reviewed_by | STRING | NULL可 | - | 承認/却下した管理者のuser_id。 |
| 8 | created_at | TIMESTAMP | NOT NULL | - | リクエスト日時。 |
| 9 | reviewed_at | TIMESTAMP | NULL可 | - | 承認/却下日時。 |

- 主キー: request_id

### 2.5. raw.notification_log

通知送信ログ。LINE無料枠の管理に使用。

| No | カラム名 | 型 | NULL | デフォルト | 説明 |
|---|---|---|---|---|---|
| 1 | notification_id | STRING | NOT NULL | - | 主キー。UUID。 |
| 2 | user_id | STRING | NOT NULL | - | 送信先ユーザー。 |
| 3 | notification_type | STRING | NOT NULL | - | start / 3day / 7day / weekly_ranking / monthly_ranking。 |
| 4 | status | STRING | NOT NULL | - | sent / failed / suppressed。 |
| 5 | sent_at | TIMESTAMP | NOT NULL | - | 送信日時。 |

- 主キー: notification_id
DOCEOF

# ============================================================
# データ定義書を追記（Part 2: Staging層〜Mart層ディメンション）
# ============================================================

cat << 'DOCEOF' >> docs/data_dictionary.md

---

## 3. Staging層

### 3.1. staging.stg_training_log

クレンジング済みトレーニングログ。dbtで生成。

| No | カラム名 | 型 | NULL | 説明 | 変換ロジック |
|---|---|---|---|---|---|
| 1 | log_id | STRING | NOT NULL | 主キー | そのまま |
| 2 | user_id | STRING | NOT NULL | ユーザーID | そのまま |
| 3 | exercise_name | STRING | NOT NULL | 種目名 | LOWER(TRIM()) |
| 4 | body_part | STRING | NOT NULL | 部位名 | LOWER(TRIM()) |
| 5 | training_date | DATE | NOT NULL | 実施日 | そのまま |
| 6 | set_number | INT64 | NOT NULL | セット番号 | そのまま |
| 7 | weight_kg | FLOAT64 | NOT NULL | 重量 | ROUND(, 1) |
| 8 | reps | INT64 | NOT NULL | レップ数 | そのまま |
| 9 | volume | FLOAT64 | NOT NULL | ボリューム | ROUND(weight_kg * reps, 1) |
| 10 | rpe | FLOAT64 | NULL可 | RPE | 6.0-10.0範囲外はNULL |
| 11 | memo | STRING | NULL可 | メモ | そのまま |
| 12 | created_at | TIMESTAMP | NOT NULL | 作成日時 | そのまま |
| 13 | updated_at | TIMESTAMP | NOT NULL | 更新日時 | そのまま |

- マテリアライズ: incremental
- ユニークキー: log_id
- パーティション: training_date（MONTH）
- 重複排除: log_id ごとに updated_at DESC で最新を採用
- フィルタ: is_deleted = FALSE

---

## 4. Mart層 - ディメンション

### 4.1. mart.d_body_part

部位マスタ。6部位（5分割法＋その他）。

| No | カラム名 | 型 | NULL | 説明 |
|---|---|---|---|---|
| 1 | body_part_id | STRING | NOT NULL | 主キー。chest/back/shoulder/leg/arm/other。 |
| 2 | body_part_name | STRING | NOT NULL | 表示名。胸/背中/肩/脚/腕/その他。 |
| 3 | training_day | STRING | NULL可 | 曜日（その他はNULL）。 |
| 4 | sort_order | INT64 | NOT NULL | 表示順。 |

- マテリアライズ: table
- レコード数: 6件（固定）

データ:

| body_part_id | body_part_name | training_day | sort_order |
|---|---|---|---|
| chest | 胸 | Monday | 1 |
| back | 背中 | Tuesday | 2 |
| shoulder | 肩 | Wednesday | 3 |
| leg | 脚 | Thursday | 4 |
| arm | 腕 | Friday | 5 |
| other | その他 | NULL | 6 |

### 4.2. mart.d_exercise

種目マスタ。有効な種目のみ。

| No | カラム名 | 型 | NULL | 説明 |
|---|---|---|---|---|
| 1 | exercise_id | STRING | NOT NULL | 主キー。例: bench_press。 |
| 2 | exercise_name | STRING | NOT NULL | 種目名。例: ベンチプレス。 |
| 3 | body_part_id | STRING | NOT NULL | 部位ID。FK → d_body_part。 |
| 4 | is_compound | BOOL | NOT NULL | 複合種目フラグ（KPI対象）。 |
| 5 | is_active | BOOL | NOT NULL | 有効フラグ。 |
| 6 | display_order | INT64 | NOT NULL | 表示順。 |
| 7 | updated_at | TIMESTAMP | NOT NULL | 更新日時。 |

- マテリアライズ: table
- フィルタ: is_active = TRUE
- ソース: raw.exercise_master

KPI対象種目（is_compound = TRUE）:

| exercise_id | exercise_name | body_part_id |
|---|---|---|
| bench_press | ベンチプレス | chest |
| half_deadlift | ハーフデッドリフト | back |
| overhead_press | オーバーヘッドプレス | shoulder |
| squat | スクワット | leg |

### 4.3. mart.d_user

ユーザーマスタ。有効なユーザーのみ。

| No | カラム名 | 型 | NULL | 説明 |
|---|---|---|---|---|
| 1 | user_id | STRING | NOT NULL | 主キー。例: user_001。 |
| 2 | user_name | STRING | NOT NULL | 表示名。 |
| 3 | line_user_id | STRING | NOT NULL | LINE userId。 |
| 4 | is_admin | BOOL | NOT NULL | 管理者フラグ。 |
| 5 | is_active | BOOL | NOT NULL | 有効フラグ。 |
| 6 | created_at | TIMESTAMP | NOT NULL | 作成日時。 |

- マテリアライズ: table
- フィルタ: is_active = TRUE
- ソース: raw.user_master
DOCEOF

# ============================================================
# データ定義書を追記（Part 3: ファクト〜メトリクス）
# ============================================================

cat << 'DOCEOF' >> docs/data_dictionary.md

---

## 5. Mart層 - ファクト

### 5.1. mart.fct_training_set

トレーニング記録。ディメンション結合済み。分析の中心テーブル。

| No | カラム名 | 型 | NULL | 説明 | ソース |
|---|---|---|---|---|---|
| 1 | log_id | STRING | NOT NULL | 主キー | stg_training_log |
| 2 | user_id | STRING | NOT NULL | ユーザーID | stg_training_log |
| 3 | training_date | DATE | NOT NULL | 実施日 | stg_training_log |
| 4 | exercise_id | STRING | NULL可 | 種目ID | d_exercise（JOIN） |
| 5 | exercise_name | STRING | NOT NULL | 種目名 | d_exercise（JOIN） |
| 6 | is_compound | BOOL | NULL可 | 複合種目フラグ | d_exercise（JOIN） |
| 7 | body_part_id | STRING | NULL可 | 部位ID | d_body_part（JOIN） |
| 8 | body_part_name | STRING | NULL可 | 部位名 | d_body_part（JOIN） |
| 9 | set_number | INT64 | NOT NULL | セット番号 | stg_training_log |
| 10 | weight_kg | FLOAT64 | NOT NULL | 重量 (kg) | stg_training_log |
| 11 | reps | INT64 | NOT NULL | レップ数 | stg_training_log |
| 12 | volume | FLOAT64 | NOT NULL | ボリューム（weight_kg × reps） | stg_training_log |
| 13 | rpe | FLOAT64 | NULL可 | RPE (6.0-10.0) | stg_training_log |
| 14 | memo | STRING | NULL可 | メモ | stg_training_log |
| 15 | created_at | TIMESTAMP | NOT NULL | 作成日時 | stg_training_log |

- マテリアライズ: incremental
- ユニークキー: log_id
- パーティション: training_date（MONTH）
- JOIN: stg_training_log → d_exercise（exercise_name）→ d_body_part（body_part_id）

---

## 6. Mart層 - メトリクス

### 6.1. mart.m_progress_curve

KPI: 7日間移動平均ボリュームと週次変化率。

| No | カラム名 | 型 | NULL | 説明 |
|---|---|---|---|---|
| 1 | user_id | STRING | NOT NULL | ユーザーID |
| 2 | exercise_id | STRING | NOT NULL | 種目ID |
| 3 | exercise_name | STRING | NOT NULL | 種目名 |
| 4 | is_compound | BOOL | NOT NULL | 複合種目フラグ |
| 5 | metric_date | DATE | NOT NULL | 計測日 |
| 6 | daily_volume | FLOAT64 | NOT NULL | 日次ボリューム合計 |
| 7 | volume_7d_ma | FLOAT64 | NOT NULL | 7日間移動平均ボリューム |
| 8 | total_sets | INT64 | NOT NULL | 日次セット数 |
| 9 | max_weight | FLOAT64 | NOT NULL | 日次最大重量 |
| 10 | wow_change_pct | FLOAT64 | NULL可 | 週次変化率（%）。目標: 1.0%以上。 |

- マテリアライズ: table
- 参照元: Streamlit ダッシュボード

### 6.2. mart.m_last_training

通知判定用。最終トレーニング日と経過日数。

| No | カラム名 | 型 | NULL | 説明 |
|---|---|---|---|---|
| 1 | user_id | STRING | NOT NULL | ユーザーID |
| 2 | body_part_id | STRING | NOT NULL | 部位ID |
| 3 | body_part_name | STRING | NOT NULL | 部位名 |
| 4 | last_training_date | DATE | NOT NULL | 部位別の最終トレーニング日 |
| 5 | days_since_last_bodypart | INT64 | NOT NULL | 部位別の経過日数 |
| 6 | days_since_last_any | INT64 | NOT NULL | 全体の経過日数 |
| 7 | needs_3day_reminder | BOOL | NOT NULL | 3日以上トレーニングなしフラグ |
| 8 | needs_7day_reminder | BOOL | NOT NULL | 部位別7日以上空きフラグ（その他は常にFALSE） |

- マテリアライズ: table
- 参照元: Cloud Functions（通知判定）
- 特記: body_part_id = other の場合 needs_7day_reminder は常に FALSE

### 6.3. mart.m_ranking_weekly

週間ボリュームランキング。締日: 日曜日。

| No | カラム名 | 型 | NULL | 説明 |
|---|---|---|---|---|
| 1 | user_id | STRING | NOT NULL | ユーザーID |
| 2 | user_name | STRING | NOT NULL | 表示名 |
| 3 | week_start | DATE | NOT NULL | 週の開始日（月曜） |
| 4 | week_end | DATE | NOT NULL | 週の終了日（日曜） |
| 5 | total_volume | FLOAT64 | NOT NULL | 週間総ボリューム（全種目） |
| 6 | rank | INT64 | NOT NULL | 順位 |
| 7 | prev_rank | INT64 | NULL可 | 前週の順位 |
| 8 | prev_volume | FLOAT64 | NULL可 | 前週のボリューム |
| 9 | rank_change | STRING | NOT NULL | 変動（UP / DOWN / SAME / NEW） |
| 10 | rank_diff | INT64 | NULL可 | 順位変動数 |

- マテリアライズ: table
- 参照元: Streamlit ランキング画面、LINE通知（毎週月曜）

### 6.4. mart.m_ranking_monthly

月間ボリュームランキング。締日: 末日。

| No | カラム名 | 型 | NULL | 説明 |
|---|---|---|---|---|
| 1 | user_id | STRING | NOT NULL | ユーザーID |
| 2 | user_name | STRING | NOT NULL | 表示名 |
| 3 | month | DATE | NOT NULL | 月（月初日） |
| 4 | total_volume | FLOAT64 | NOT NULL | 月間総ボリューム（全種目） |
| 5 | rank | INT64 | NOT NULL | 順位 |
| 6 | prev_rank | INT64 | NULL可 | 前月の順位 |
| 7 | prev_volume | FLOAT64 | NULL可 | 前月のボリューム |
| 8 | rank_change | STRING | NOT NULL | 変動（UP / DOWN / SAME / NEW） |
| 9 | rank_diff | INT64 | NULL可 | 順位変動数 |

- マテリアライズ: table
- 参照元: Streamlit ランキング画面、LINE通知（毎月1日）

### 6.5. mart.m_ranking_alltime

全期間ボリュームランキング。

| No | カラム名 | 型 | NULL | 説明 |
|---|---|---|---|---|
| 1 | user_id | STRING | NOT NULL | ユーザーID |
| 2 | user_name | STRING | NOT NULL | 表示名 |
| 3 | total_volume | FLOAT64 | NOT NULL | 全期間総ボリューム（全種目） |
| 4 | rank | INT64 | NOT NULL | 順位 |

- マテリアライズ: table
- 参照元: Streamlit ランキング画面

### 6.6. mart.m_ranking_bodypart

部位別ランキング。週間/月間/全期間。

| No | カラム名 | 型 | NULL | 説明 |
|---|---|---|---|---|
| 1 | user_id | STRING | NOT NULL | ユーザーID |
| 2 | user_name | STRING | NOT NULL | 表示名 |
| 3 | body_part_id | STRING | NOT NULL | 部位ID |
| 4 | body_part_name | STRING | NOT NULL | 部位名 |
| 5 | period_type | STRING | NOT NULL | weekly / monthly / alltime |
| 6 | period_start | DATE | NULL可 | 期間開始日（alltimeはNULL） |
| 7 | total_volume | FLOAT64 | NOT NULL | 期間内の部位別総ボリューム |
| 8 | rank | INT64 | NOT NULL | 順位 |

- マテリアライズ: table
- 参照元: Streamlit ランキング画面

### 6.7. mart.m_personal_record

個人記録（最高重量・最高ボリューム）と更新フラグ。

| No | カラム名 | 型 | NULL | 説明 |
|---|---|---|---|---|
| 1 | user_id | STRING | NOT NULL | ユーザーID |
| 2 | user_name | STRING | NOT NULL | 表示名 |
| 3 | exercise_id | STRING | NOT NULL | 種目ID |
| 4 | exercise_name | STRING | NOT NULL | 種目名 |
| 5 | record_type | STRING | NOT NULL | max_weight / max_volume |
| 6 | record_value | FLOAT64 | NOT NULL | 記録値 |
| 7 | achieved_date | DATE | NOT NULL | 達成日 |
| 8 | previous_value | FLOAT64 | NULL可 | 前回の記録値 |
| 9 | is_new | BOOL | NOT NULL | 直近7日以内に達成されたか |

- マテリアライズ: table
- 参照元: Streamlit ソーシャル画面（記録更新フィード）
- 特記: is_new = TRUE のレコードがフィードに表示される

### 6.8. mart.m_calendar

カレンダー表示用。日別サマリー。

| No | カラム名 | 型 | NULL | 説明 |
|---|---|---|---|---|
| 1 | user_id | STRING | NOT NULL | ユーザーID |
| 2 | training_date | DATE | NOT NULL | トレーニング日 |
| 3 | body_parts | STRING | NOT NULL | その日の部位一覧（カンマ区切り） |
| 4 | total_volume | FLOAT64 | NOT NULL | その日の総ボリューム |
| 5 | exercise_count | INT64 | NOT NULL | その日の種目数 |
| 6 | exercise_summary | STRING | NOT NULL | 種目サマリー（詳細表示用） |

- マテリアライズ: table
- 参照元: Streamlit カレンダー画面
DOCEOF

---

## 7. Mart層 - ML

### 7.1. mart.training_predictor（BigQuery MLモデル）

次回トレーニングの推奨重量を予測するBigQuery MLモデル。テーブルではなくモデルオブジェクト。

#### モデル概要

| 項目 | 詳細 |
|---|---|
| モデルタイプ | BOOSTED_TREE_REGRESSOR |
| 目的変数 | next_weight_kg（次回の使用重量） |
| 再学習頻度 | 週次（毎週月曜 daily-pipeline 内で実行） |
| 再学習トリガー | Cloud Functions（dbt-runner）から月曜のみ実行 |
| 学習データ | mart.fct_training_set から生成した連続セッションペア |
| モデルバージョン管理 | CREATE OR REPLACE で上書き（最新1世代のみ保持） |

#### ハイパーパラメータ

| パラメータ | 値 | 説明 |
|---|---|---|
| model_type | BOOSTED_TREE_REGRESSOR | 勾配ブースティング回帰木 |
| input_label_cols | ['next_weight_kg'] | 目的変数 |
| num_trials | 5 | ハイパーパラメータチューニングの試行回数 |
| max_iterations | 50 | 最大イテレーション数 |
| early_stop | TRUE | 早期停止有効 |
| data_split_method | AUTO_SPLIT | 学習/検証データの自動分割 |

#### 特徴量（入力）

| No | 特徴量名 | 型 | 説明 | 生成ロジック |
|---|---|---|---|---|
| 1 | prev_weight_kg | FLOAT64 | 前回の使用重量 (kg) | LAG(weight_kg) OVER (PARTITION BY user_id, exercise_id, set_number ORDER BY training_date) |
| 2 | prev_reps | INT64 | 前回のレップ数 | LAG(reps) OVER (同上) |
| 3 | prev_rpe | FLOAT64 | 前回のRPE | LAG(rpe) OVER (同上) |
| 4 | prev_volume | FLOAT64 | 前回のボリューム | LAG(volume) OVER (同上) |
| 5 | set_number | INT64 | セット番号 | そのまま |
| 6 | days_since_last | INT64 | 前回からの経過日数 | DATE_DIFF(training_date, LAG(training_date) OVER (同上), DAY) |

#### 目的変数（出力）

| No | カラム名 | 型 | 説明 |
|---|---|---|---|
| 1 | predicted_next_weight_kg | FLOAT64 | 予測される次回の使用重量 (kg) |

#### 学習データの前提条件

- `prev_weight_kg IS NOT NULL`（前回記録が存在するペアのみ）
- `days_since_last IS NOT NULL`（連続セッションのみ）
- ユーザー・種目・セット番号ごとに時系列でペアを生成

#### 学習データ例

| prev_weight_kg | prev_reps | prev_rpe | prev_volume | set_number | days_since_last | next_weight_kg |
|---|---|---|---|---|---|---|
| 77.5 | 5 | 8.0 | 387.5 | 1 | 4 | 80.0 |
| 82.5 | 3 | 8.5 | 247.5 | 2 | 4 | 85.0 |
| 87.5 | 1 | 9.5 | 87.5 | 3 | 4 | 90.0 |

#### モデル評価指標

再学習後に以下のクエリで評価可能:

```sql
SELECT *
FROM ML.EVALUATE(MODEL `mart.training_predictor`)

| 指標 | 説明 | 目安 |
| --- | --- | --- |
| mean_absolute_error | 平均絶対誤差 | ≦ 5.0 kg |
| mean_squared_error | 平均二乗誤差 | - |
| r2_score | 決定係数 | ≧ 0.7 |

#### 注意事項
- データ量が少ない初期段階（各ユーザー10セッション未満）では予測精度が低い
- 精度が低い場合はフォールバックロジック（SQL単純提案）が使用される
- モデルの再学習は `CREATE OR REPLACE` で行うため、一時的にモデルが利用不可になる可能性がある（数秒〜数十秒）
---
### 7.2. mart.m_ml_suggestion
BigQuery MLの予測結果テーブル。各ユーザー・種目・セットごとの次回推奨値。
| No | カラム名 | 型 | NULL | 説明 |
|---|---|---|---|---|
| 1 | user_id | STRING | NOT NULL | ユーザーID |
| 2 | exercise_id | STRING | NOT NULL | 種目ID |
| 3 | exercise_name | STRING | NOT NULL | 種目名 |
| 4 | set_number | INT64 | NOT NULL | セット番号 |
| 5 | current_weight_kg | FLOAT64 | NOT NULL | 直近の使用重量 (kg) |
| 6 | current_reps | INT64 | NOT NULL | 直近のレップ数 |
| 7 | current_rpe | FLOAT64 | NULL可 | 直近のRPE |
| 8 | suggested_weight_kg | FLOAT64 | NOT NULL | 推奨重量 (kg)。ROUND(, 1)。 |
| 9 | suggested_reps | INT64 | NOT NULL | 推奨レップ数 |
| 10 | suggested_volume | FLOAT64 | NOT NULL | 推奨ボリューム（suggested_weight_kg × suggested_reps） |
| 11 | suggested_date | DATE | NOT NULL | 提案生成日 |
| 12 | model_version | STRING | NOT NULL | モデルバージョン（例: boosted_tree_v1） |
- マテリアライズ: table
- 参照元: Streamlit Input画面（今回の提案）
- 更新タイミング: 日次（dbt run）+ MLモデル再学習後（月曜）
#### 推奨レップ数のロジック
| 直近RPE | 推奨レップ数 | 理由 |
|---|---|---|
| ≧ 9.5 | 前回と同じ | 限界に近い → 回数維持で重量適応を優先 |
| ≦ 7.0 | 前回 + 2 | 余裕あり → 回数を増やしてボリューム増加 |
| 7.0 < RPE < 9.5 | 前回と同じ | 適正範囲 → 現状維持でMLの重量提案に従う |
#### フォールバックロジック
MLモデルの予測結果が存在しない場合（初期段階・データ不足時）に使用される。
| 直近RPE | 推奨重量 | 推奨レップ数 | 理由 |
|---|---|---|---|
| ≧ 9.5 | 前回と同じ | 前回 + 1 | きつかった → 重量据え置きで回数微増 |
| ≦ 7.0 | 前回 × 1.05（5%増） | 前回と同じ | 余裕あり → 重量を大きめに増加 |
| 7.0 < RPE < 9.5 | 前回 × 1.025（2.5%増） | 前回と同じ | 通常 → 漸進的に重量増加 |
| RPE未入力 | 前回 × 1.025（2.5%増） | 前回と同じ | デフォルト → 漸進的に重量増加 |
#### 提案の表示例（Streamlit Input画面）
MLモデルによる提案の場合:
    💡 今回の提案（🤖 AIモデル）
    セット  重量      回数    推奨ボリューム
    1      80.0 kg   5      400.0 kg
    2      85.0 kg   3      255.0 kg
    3      90.0 kg   1      90.0 kg
    📊 提案通りの総負荷量: 745.0 kg
       (前回総負荷量: 720.0 kg  +3.5%)
フォールバック提案の場合:
    💡 今回の提案（📈 過去実績ベース）
    セット  重量      回数    推奨ボリューム
    1      79.4 kg   5      397.0 kg
    2      84.6 kg   3      253.8 kg
    3      89.7 kg   1      89.7 kg
    📊 提案通りの総負荷量: 740.5 kg
       (前回総負荷量: 720.0 kg  +2.8%)
    ℹ️ データが蓄積されるとAIモデルによる提案に切り替わります
#### データ例
| user_id | exercise_id | exercise_name | set_number | current_weight_kg | current_reps | current_rpe | suggested_weight_kg | suggested_reps | suggested_volume | suggested_date | model_version |
|---|---|---|---|---|---|---|---|---|---|---|---|
| user_001 | bench_press | ベンチプレス | 1 | 77.5 | 5 | 8.0 | 80.0 | 5 | 400.0 | 2025-01-20 | boosted_tree_v1 |
| user_001 | bench_press | ベンチプレス | 2 | 82.5 | 3 | 8.5 | 85.0 | 3 | 255.0 | 2025-01-20 | boosted_tree_v1 |
| user_001 | bench_press | ベンチプレス | 3 | 87.5 | 1 | 9.5 | 90.0 | 1 | 90.0 | 2025-01-20 | boosted_tree_v1 |
---
## 8. テーブル間リレーション
### 8.1. 外部キー関係
| 参照元テーブル | 参照元カラム | 参照先テーブル | 参照先カラム | 関係 |
|---|---|---|---|---|
| raw.training_log | user_id | raw.user_master | user_id | N:1 |
| raw.training_log | exercise_name | raw.exercise_master | exercise_name | N:1 |
| raw.exercise_master | body_part_id | mart.d_body_part | body_part_id | N:1 |
| raw.exercise_request | user_id | raw.user_master | user_id | N:1 |
| raw.exercise_request | body_part_id | mart.d_body_part | body_part_id | N:1 |
| raw.exercise_request | reviewed_by | raw.user_master | user_id | N:1 |
| raw.notification_log | user_id | raw.user_master | user_id | N:1 |
| staging.stg_training_log | log_id | raw.training_log | log_id | 1:1 |
| mart.fct_training_set | user_id | mart.d_user | user_id | N:1 |
| mart.fct_training_set | exercise_id | mart.d_exercise | exercise_id | N:1 |
| mart.fct_training_set | body_part_id | mart.d_body_part | body_part_id | N:1 |
| mart.d_exercise | body_part_id | mart.d_body_part | body_part_id | N:1 |
| mart.m_progress_curve | user_id | mart.d_user | user_id | N:1 |
| mart.m_progress_curve | exercise_id | mart.d_exercise | exercise_id | N:1 |
| mart.m_last_training | user_id | mart.d_user | user_id | N:1 |
| mart.m_last_training | body_part_id | mart.d_body_part | body_part_id | N:1 |
| mart.m_ranking_weekly | user_id | mart.d_user | user_id | N:1 |
| mart.m_ranking_monthly | user_id | mart.d_user | user_id | N:1 |
| mart.m_ranking_alltime | user_id | mart.d_user | user_id | N:1 |
| mart.m_ranking_bodypart | user_id | mart.d_user | user_id | N:1 |
| mart.m_ranking_bodypart | body_part_id | mart.d_body_part | body_part_id | N:1 |
| mart.m_personal_record | user_id | mart.d_user | user_id | N:1 |
| mart.m_personal_record | exercise_id | mart.d_exercise | exercise_id | N:1 |
| mart.m_calendar | user_id | mart.d_user | user_id | N:1 |
| mart.m_ml_suggestion | user_id | mart.d_user | user_id | N:1 |
| mart.m_ml_suggestion | exercise_id | mart.d_exercise | exercise_id | N:1 |
### 8.2. データフロー（依存関係）
    raw.user_master
      └── mart.d_user
    raw.exercise_master
      └── mart.d_exercise
    mart.d_body_part (seed / 静的定義)
    raw.training_log
      └── staging.stg_training_log
            └── mart.fct_training_set  ← JOIN: d_user, d_exercise, d_body_part
                  ├── mart.m_progress_curve
                  ├── mart.m_last_training
                  ├── mart.m_ranking_weekly
                  ├── mart.m_ranking_monthly
                  ├── mart.m_ranking_alltime
                  ├── mart.m_ranking_bodypart
                  ├── mart.m_personal_record
                  ├── mart.m_calendar
                  └── mart.training_predictor (MLモデル)
                        └── mart.m_ml_suggestion

    raw.exercise_request (独立。mart層への依存なし)

    raw.notification_log (独立。mart層への依存なし)

### 8.3. dbt実行順序（DAG）

dbt runで実行されるモデルの順序:

    第1層（ソース参照のみ）:
      ├── mart.d_body_part      ← seed
      ├── mart.d_exercise       ← raw.exercise_master
      ├── mart.d_user           ← raw.user_master
      └── staging.stg_training_log ← raw.training_log

    第2層（staging + ディメンション参照）:
      └── mart.fct_training_set ← stg_training_log + d_user + d_exercise + d_body_part

    第3層（ファクト参照）:
      ├── mart.m_progress_curve    ← fct_training_set
      ├── mart.m_last_training     ← fct_training_set
      ├── mart.m_ranking_weekly    ← fct_training_set + d_user
      ├── mart.m_ranking_monthly   ← fct_training_set + d_user
      ├── mart.m_ranking_alltime   ← fct_training_set + d_user
      ├── mart.m_ranking_bodypart  ← fct_training_set + d_user + d_body_part
      ├── mart.m_personal_record   ← fct_training_set + d_user
      └── mart.m_calendar          ← fct_training_set

    第4層（MLモデル ※dbt外で実行）:
      └── mart.training_predictor  ← fct_training_set（Cloud Functionsから月曜のみ実行）

    第5層（ML予測結果）:
      └── mart.m_ml_suggestion     ← fct_training_set + training_predictor

### 8.4. レイヤー間のデータ量見積もり

3ユーザー、各ユーザー週5回トレーニング、1回あたり平均4種目×3セットの前提:

| テーブル | 1日あたり | 1週間あたり | 1ヶ月あたり | 1年あたり |
|---|---|---|---|---|
| raw.training_log | 約36行 | 約180行 | 約780行 | 約9,360行 |
| staging.stg_training_log | 約36行 | 約180行 | 約780行 | 約9,360行 |
| mart.fct_training_set | 約36行 | 約180行 | 約780行 | 約9,360行 |
| mart.m_progress_curve | 約12行/日 | 約84行 | 約360行 | 約4,320行 |
| mart.m_last_training | 18行（固定: 3ユーザー × 6部位） | - | - | - |
| mart.m_ranking_weekly | 3行/週 | 3行 | 約12行 | 約156行 |
| mart.m_ranking_monthly | 3行/月 | - | 3行 | 約36行 |
| mart.m_ranking_alltime | 3行（固定） | - | - | - |
| mart.m_ranking_bodypart | 最大54行/期間 | - | - | - |
| mart.m_personal_record | 最大約100行 | - | - | - |
| mart.m_calendar | 約3行/日 | 約15行 | 約65行 | 約780行 |
| mart.m_ml_suggestion | 最大約150行 | - | - | - |
| raw.notification_log | 約5行 | 約40行 | 約141行 | 約1,700行 |

BigQuery無料枠（10GB Storage）に対して年間データ量は数MB程度。十分に収まる。

---

## 9. バリデーションルール

### 9.1. 入力バリデーション（Streamlit側）

トレーニング入力画面で適用されるバリデーションルール。

#### トレーニング記録入力

| No | 項目 | ルール | エラーメッセージ |
|---|---|---|---|
| 1 | training_date | 必須。未来日付は不可。過去90日以内。 | 「日付を選択してください」「未来の日付は入力できません」「90日以上前の日付は入力できません」 |
| 2 | body_part | 必須。d_body_partに存在する値のみ。 | 「部位を選択してください」 |
| 3 | exercise_name | 必須。選択した部位に紐づくd_exerciseの値のみ。 | 「種目を選択してください」 |
| 4 | set_number | 自動採番（1始まり）。1〜20の範囲。 | 「セット数の上限（20）に達しました」 |
| 5 | weight_kg | 必須。0.0〜500.0 kg。0.5kg刻み。 | 「重量は0〜500kgの範囲で入力してください」 |
| 6 | reps | 必須。1〜100の整数。 | 「回数は1〜100の範囲で入力してください」 |
| 7 | rpe | 任意。入力する場合は6.0〜10.0。0.5刻み。 | 「RPEは6.0〜10.0の範囲で入力してください」 |
| 8 | memo | 任意。最大200文字。 | 「メモは200文字以内で入力してください」 |

#### 種目追加リクエスト

| No | 項目 | ルール | エラーメッセージ |
|---|---|---|---|
| 1 | exercise_name | 必須。2〜30文字。既存種目名と重複不可。 | 「種目名を入力してください」「既に登録されている種目です」 |
| 2 | body_part_id | 必須。d_body_partに存在する値のみ。 | 「部位を選択してください」 |
| 3 | reason | 任意。最大500文字。 | 「理由は500文字以内で入力してください」 |

#### 管理者画面（種目マスタ管理）

| No | 項目 | ルール | エラーメッセージ |
|---|---|---|---|
| 1 | exercise_id | 必須。英数字とアンダースコアのみ。3〜30文字。既存IDと重複不可。 | 「種目IDは英数字とアンダースコアのみ使用可能です」「既に使用されているIDです」 |
| 2 | exercise_name | 必須。2〜30文字。既存種目名と重複不可。 | 「種目名を入力してください」「既に登録されている種目です」 |
| 3 | body_part_id | 必須。d_body_partに存在する値のみ。 | 「部位を選択してください」 |
| 4 | is_compound | 必須。BOOL。 | - |
| 5 | display_order | 必須。1〜100の整数。 | 「表示順は1〜100の範囲で入力してください」 |

### 9.2. データ品質テスト（dbt側）

dbt testで実行されるデータ品質テスト。日次バッチ（06:00 JST）で自動実行。

#### Staging層テスト

| No | モデル | カラム | テスト種別 | 内容 |
|---|---|---|---|---|
| 1 | stg_training_log | log_id | unique | 主キーの一意性 |
| 2 | stg_training_log | log_id | not_null | 主キーの非NULL |
| 3 | stg_training_log | user_id | not_null | ユーザーIDの非NULL |
| 4 | stg_training_log | exercise_name | not_null | 種目名の非NULL |
| 5 | stg_training_log | training_date | not_null | 日付の非NULL |
| 6 | stg_training_log | weight_kg | not_null | 重量の非NULL |
| 7 | stg_training_log | reps | not_null | レップ数の非NULL |
| 8 | stg_training_log | volume | not_null | ボリュームの非NULL |

#### Mart層テスト - ディメンション

| No | モデル | カラム | テスト種別 | 内容 |
|---|---|---|---|---|
| 9 | d_body_part | body_part_id | unique | 主キーの一意性 |
| 10 | d_body_part | body_part_id | not_null | 主キーの非NULL |
| 11 | d_exercise | exercise_id | unique | 主キーの一意性 |
| 12 | d_exercise | exercise_id | not_null | 主キーの非NULL |
| 13 | d_exercise | body_part_id | not_null | 部位IDの非NULL |
| 14 | d_exercise | body_part_id | accepted_values | chest/back/shoulder/leg/arm/otherのみ |
| 15 | d_user | user_id | unique | 主キーの一意性 |
| 16 | d_user | user_id | not_null | 主キーの非NULL |

#### Mart層テスト - ファクト

| No | モデル | カラム | テスト種別 | 内容 |
|---|---|---|---|---|
| 17 | fct_training_set | log_id | unique | 主キーの一意性 |
| 18 | fct_training_set | log_id | not_null | 主キーの非NULL |
| 19 | fct_training_set | user_id | not_null | ユーザーIDの非NULL |
| 20 | fct_training_set | volume | not_null | ボリュームの非NULL |

#### Mart層テスト - メトリクス

| No | モデル | カラム | テスト種別 | 内容 |
|---|---|---|---|---|
| 21 | m_progress_curve | user_id | not_null | ユーザーIDの非NULL |
| 22 | m_progress_curve | exercise_id | not_null | 種目IDの非NULL |
| 23 | m_progress_curve | metric_date | not_null | 日付の非NULL |
| 24 | m_last_training | user_id | not_null | ユーザーIDの非NULL |
| 25 | m_last_training | body_part_id | not_null | 部位IDの非NULL |
| 26 | m_ranking_weekly | rank | not_null | 順位の非NULL |
| 27 | m_ranking_monthly | rank | not_null | 順位の非NULL |
| 28 | m_ranking_alltime | rank | not_null | 順位の非NULL |
| 29 | m_ranking_bodypart | rank | not_null | 順位の非NULL |
| 30 | m_ranking_bodypart | period_type | accepted_values | weekly/monthly/alltimeのみ |
| 31 | m_personal_record | record_type | accepted_values | max_weight/max_volumeのみ |
| 32 | m_calendar | user_id | not_null | ユーザーIDの非NULL |
| 33 | m_calendar | training_date | not_null | 日付の非NULL |

#### Mart層テスト - ML

| No | モデル | カラム | テスト種別 | 内容 |
|---|---|---|---|---|
| 34 | m_ml_suggestion | user_id | not_null | ユーザーIDの非NULL |
| 35 | m_ml_suggestion | exercise_id | not_null | 種目IDの非NULL |
| 36 | m_ml_suggestion | suggested_weight_kg | not_null | 推奨重量の非NULL |
| 37 | m_ml_suggestion | suggested_reps | not_null | 推奨レップ数の非NULL |
| 38 | m_ml_suggestion | model_version | not_null | モデルバージョンの非NULL |

### 9.3. ビジネスルール

アプリケーション全体で適用されるビジネスルール。

| No | ルール名 | 対象 | 内容 |
|---|---|---|---|
| 1 | 編集制限 | raw.training_log | created_at から3時間以内のみ編集可能。超過後は読み取り専用。 |
| 2 | 論理削除 | raw.training_log | 物理削除は行わない。is_deleted = TRUE で論理削除。 |
| 3 | 管理者権限 | raw.exercise_request | status の更新（approved/rejected）は is_admin = TRUE のユーザーのみ可能。 |
| 4 | 種目一意性 | raw.exercise_master | exercise_name は全体で一意。重複登録不可。 |
| 5 | KPI対象 | mart.m_progress_curve | is_compound = TRUE の種目のみKPI（週次変化率 ≧ 1.0%）の対象。 |
| 6 | 7日通知除外 | mart.m_last_training | body_part_id = 'other' の場合、needs_7day_reminder は常に FALSE。 |
| 7 | 通知上限 | raw.notification_log | 月間200通（LINE無料枠）。180通で低優先度抑制、190通で中優先度抑制、200通で全停止。 |
| 8 | 自動保存条件 | Streamlit | weight_kg > 0 かつ reps > 0 のセットのみ保存対象。 |
| 9 | 筋トレ開始通知 | Cloud Functions | その日初回のトレーニング記録登録時のみ送信。2回目以降は送信しない。 |
| 10 | ランキング変動 | mart.m_ranking_weekly/monthly | 前回データなしの場合は rank_change = 'NEW'。 |

### 9.4. データ型の制約一覧

全テーブルで使用されるデータ型とその制約の一覧。

| データ型 | 用途 | 制約・備考 |
|---|---|---|
| STRING | ID系（log_id, user_id, exercise_id等） | UUID v4形式またはスネークケース英数字。空文字不可。 |
| STRING | 名前系（user_name, exercise_name等） | 2〜30文字。トリム済み。 |
| STRING | ステータス系（status, notification_type等） | 定義済み値のみ（ENUM相当）。 |
| DATE | 日付系（training_date等） | YYYY-MM-DD形式。タイムゾーン: Asia/Tokyo基準。 |
| TIMESTAMP | 日時系（created_at, updated_at等） | UTC格納。表示時にAsia/Tokyoに変換。 |
| INT64 | 整数系（reps, set_number, rank等） | 負の値は不可（0以上）。 |
| FLOAT64 | 小数系（weight_kg, volume, rpe等） | ROUND(, 1)で小数第1位まで。 |
| BOOL | フラグ系（is_admin, is_active, is_deleted等） | TRUE/FALSEのみ。NULL不可。 |

### 9.5. ENUM値の定義

STRING型でENUM相当として使用される値の一覧。

#### body_part_id

| 値 | 表示名 | 備考 |
|---|---|---|
| chest | 胸 | - |
| back | 背中 | - |
| shoulder | 肩 | - |
| leg | 脚 | - |
| arm | 腕 | - |
| other | その他 | 7日通知対象外 |

#### exercise_request.status

| 値 | 説明 | 遷移元 | 遷移先 |
|---|---|---|---|
| pending | 承認待ち | （初期値） | approved / rejected |
| approved | 承認済み | pending | （最終状態） |
| rejected | 却下 | pending | （最終状態） |

#### notification_log.notification_type

| 値 | 説明 | トリガー |
|---|---|---|
| start | 筋トレ開始通知 | ユーザーがその日初回の記録を登録 |
| 3day | 3日未実施リマインド | Cloud Scheduler 日次 07:00 JST |
| 7day | 7日空きリマインド（部位別） | Cloud Scheduler 日次 07:00 JST |
| weekly_ranking | 週間ランキング通知 | Cloud Scheduler 毎週月曜 08:00 JST |
| monthly_ranking | 月間ランキング通知 | Cloud Scheduler 毎月1日 08:00 JST |

#### notification_log.status

| 値 | 説明 | 備考 |
|---|---|---|
| sent | 送信成功 | LINE APIから200レスポンス |
| failed | 送信失敗 | リトライ3回後も失敗 |
| suppressed | 抑制 | 月間通知上限による抑制 |

#### m_ranking_*.rank_change

| 値 | 説明 | 表示 |
|---|---|---|
| UP | 前回より順位上昇 | ↑ |
| DOWN | 前回より順位下降 | ↓ |
| SAME | 前回と同順位 | → |
| NEW | 前回データなし（初参加） | NEW |

#### m_personal_record.record_type

| 値 | 説明 | 計算方法 |
|---|---|---|
| max_weight | 最高重量 | 種目ごとのMAX(weight_kg) |
| max_volume | 最高ボリューム（1セット） | 種目ごとのMAX(volume) |

#### input_source

| 値 | 説明 | 備考 |
|---|---|---|
| streamlit | Streamlit Cloudからの入力 | 現時点で唯一の入力元 |

### 9.6. パーティション・クラスタリング設計

| テーブル | パーティション | パーティションキー | 粒度 | クラスタリングキー |
|---|---|---|---|---|
| raw.training_log | あり | training_date | DAY | - |
| staging.stg_training_log | あり | training_date | MONTH | - |
| mart.fct_training_set | あり | training_date | MONTH | - |
| その他のmart.* | なし | - | - | - |

パーティション設計の理由:
- トレーニングログは日付での絞り込みが頻繁に発生するため、パーティションで読み取りコストを削減
- raw層はDAY粒度（書き込み頻度が高い）、staging/mart層はMONTH粒度（バッチ更新のため）
- メトリクス系テーブルはデータ量が少ないためパーティション不要

---

## 10. 付録

### 10.1. 命名規則

| 対象 | 規則 | 例 |
|---|---|---|
| データセット名 | スネークケース。レイヤー名と一致。 | raw, staging, mart |
| テーブル名（Raw） | スネークケース。エンティティ名。 | training_log, exercise_master |
| テーブル名（Staging） | `stg_` プレフィックス + ソーステーブル名。 | stg_training_log |
| テーブル名（Mart/ディメンション） | `d_` プレフィックス + エンティティ名。 | d_user, d_exercise, d_body_part |
| テーブル名（Mart/ファクト） | `fct_` プレフィックス + エンティティ名。 | fct_training_set |
| テーブル名（Mart/メトリクス） | `m_` プレフィックス + メトリクス名。 | m_ranking_weekly, m_calendar |
| テーブル名（Mart/ML） | `ml_` プレフィックス（モデル）または `m_ml_` プレフィックス（結果）。 | training_predictor, m_ml_suggestion |
| カラム名 | スネークケース。 | user_id, training_date, weight_kg |
| 主キー | テーブルのエンティティ名 + `_id`。 | log_id, user_id, exercise_id |
| 外部キー | 参照先テーブルの主キーと同名。 | user_id, body_part_id |
| フラグ系 | `is_` プレフィックス。 | is_admin, is_active, is_deleted, is_compound |
| 日付系 | `_date` サフィックス。 | training_date, achieved_date |
| 日時系 | `_at` サフィックス。 | created_at, updated_at, sent_at |
| 数値（計算値） | 意味のある名前。単位をサフィックスに含める。 | weight_kg, volume, days_since_last |

### 10.2. タイムゾーン規約

| 項目 | 規約 |
|---|---|
| データ格納（TIMESTAMP） | UTC |
| データ格納（DATE） | Asia/Tokyo基準の日付 |
| 表示（Streamlit） | Asia/Tokyo（JSTに変換して表示） |
| スケジューラ（Cloud Scheduler） | Asia/Tokyo |
| ログ出力 | UTC（Cloud Loggingのデフォルト） |
| dbt内のCURRENT_DATE() | `CURRENT_DATE('Asia/Tokyo')` を使用 |
| dbt内のCURRENT_TIMESTAMP() | UTC（BigQueryのデフォルト） |

### 10.3. 変更履歴

| 日付 | バージョン | 変更内容 |
|---|---|---|
| 2025/XX/XX | 1.0 | 初版作成 |

