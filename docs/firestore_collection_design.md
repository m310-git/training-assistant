# Firestore コレクション設計
更新日: 2026-04-12

## 1. 概要

本設計では、Streamlit の入力画面高速化を目的として、  
**当日入力・保存・編集・復元に必要なデータを Firestore に保存**する。

BigQuery は引き続き以下の用途で利用する。

- ランキング
- ダッシュボード
- カレンダー
- ソーシャル
- ML提案
- dbt による staging / mart 変換

Firestore は **入力系の一次保存先**、BigQuery は **分析系の参照先** として責務を分離する。

---

## 2. 設計方針

### 2.1. 目的

以下を満たすことを目的とする。

- 1ユーザー / 1日 / 1種目 の入力を高速に復元できる
- セット単位の編集がしやすい
- BigQuery `raw.training_log` に変換しやすい
- 小規模構成で保守しやすい
- 将来の BigQuery 同期処理に対応しやすい

### 2.2. 初期方針

初期フェーズでは以下のシンプルな構造を採用する。

- トップレベルコレクションは 1つ
- 1ドキュメント = 1ユーザー × 1日 × 1種目
- セットは `sets` 配列で保持
- 削除は物理削除ではなく論理削除
- 同期状態をドキュメントに持つ

---

## 3. コレクション構成

### 3.1. 採用コレクション

- `training_logs`

### 3.2. ドキュメント単位

1ドキュメントは以下の単位で管理する。

- `1ユーザー × 1日 × 1種目`

### 3.3. ドキュメントID

以下の形式を採用する。

~~~text
{user_id}_{training_date}_{exercise_id}
~~~

例:

~~~text
user_001_2026-04-12_bench_press
user_001_2026-04-12_squat
user_002_2026-04-12_lat_pulldown
~~~

### 3.4. この構成を採用する理由

- Input 画面が必要とする参照単位に一致する
- 当日復元時に 1ドキュメント read で済む
- BigQuery 同期時に 1ドキュメントを複数セットへ展開しやすい
- 実装が単純で保守しやすい

---

## 4. ドキュメントスキーマ

### 4.1. 全体構造例

~~~json
{
  "doc_id": "user_001_2026-04-12_bench_press",
  "user_id": "user_001",
  "user_name": "山田",
  "training_date": "2026-04-12",
  "body_part_id": "chest",
  "body_part_name": "胸",
  "exercise_id": "bench_press",
  "exercise_name": "ベンチプレス",
  "input_source": "streamlit",
  "status": "active",
  "is_deleted": false,
  "sets": [
    {
      "set_id": "0e7d54e4-3e90-4c7b-9d82-3e0c94b0d111",
      "set_number": 1,
      "weight_kg": 80.0,
      "reps": 5,
      "rpe": null,
      "memo": "",
      "is_deleted": false,
      "created_at": "2026-04-12T10:00:00+00:00",
      "updated_at": "2026-04-12T10:00:00+00:00"
    },
    {
      "set_id": "c1b7d92c-71c1-4f23-8d6f-d3c3b7182222",
      "set_number": 2,
      "weight_kg": 85.0,
      "reps": 3,
      "rpe": null,
      "memo": "少し重い",
      "is_deleted": false,
      "created_at": "2026-04-12T10:00:00+00:00",
      "updated_at": "2026-04-12T10:05:00+00:00"
    }
  ],
  "set_count": 2,
  "total_volume": 655.0,
  "created_at": "2026-04-12T10:00:00+00:00",
  "updated_at": "2026-04-12T10:05:00+00:00",
  "last_edited_at": "2026-04-12T10:05:00+00:00",
  "editable_until": "2026-04-12T13:00:00+00:00",
  "sync_status": "pending",
  "synced_at": null,
  "sync_version": 1,
  "schema_version": 1
}
~~~

---

## 5. フィールド定義

### 5.1. ドキュメント共通フィールド

| フィールド名 | 型 | 必須 | 説明 |
|---|---|---:|---|
| `doc_id` | string | 任意 | ドキュメントIDを冗長保持 |
| `user_id` | string | 必須 | ユーザーID |
| `user_name` | string | 任意 | 表示用ユーザー名 |
| `training_date` | string | 必須 | `YYYY-MM-DD` |
| `body_part_id` | string | 必須 | 部位ID |
| `body_part_name` | string | 任意 | 表示用部位名 |
| `exercise_id` | string | 必須 | 種目ID |
| `exercise_name` | string | 必須 | 種目名 |
| `input_source` | string | 必須 | 例: `streamlit` |
| `status` | string | 必須 | `active` / `deleted` / `archived` |
| `is_deleted` | bool | 必須 | ドキュメント全体の論理削除フラグ |
| `sets` | array<object> | 必須 | セット情報の配列 |
| `set_count` | number | 必須 | 有効セット数 |
| `total_volume` | number | 必須 | 有効セットの総負荷量 |
| `created_at` | string or timestamp | 必須 | 初回作成日時 |
| `updated_at` | string or timestamp | 必須 | 最終更新日時 |
| `last_edited_at` | string or timestamp | 必須 | 最終編集日時 |
| `editable_until` | string or timestamp | 必須 | 編集期限 |
| `sync_status` | string | 必須 | `pending` / `synced` / `failed` |
| `synced_at` | string or timestamp or null | 任意 | 最終同期日時 |
| `sync_version` | number | 必須 | 同期バージョン |
| `schema_version` | number | 必須 | スキーマバージョン |

---

## 6. `sets` 配列の定義

### 6.1. セット項目

| フィールド名 | 型 | 必須 | 説明 |
|---|---|---:|---|
| `set_id` | string | 必須 | セット単位の一意ID |
| `set_number` | number | 必須 | 表示順。1始まり |
| `weight_kg` | number | 必須 | 重量 |
| `reps` | number | 必須 | 回数 |
| `rpe` | number or null | 任意 | RPE |
| `memo` | string | 任意 | メモ |
| `is_deleted` | bool | 必須 | セット論理削除フラグ |
| `created_at` | string or timestamp | 必須 | セット初回作成日時 |
| `updated_at` | string or timestamp | 必須 | セット更新日時 |

### 6.2. `set_id` を持つ理由

`set_number` は並び替えや削除で変わる可能性があるため、  
更新・削除・同期の識別子としては不安定である。

そのため、各セットには以下を満たす一意な `set_id` を付与する。

- セット単位の論理削除がしやすい
- BigQuery 同期時に `log_id` として流用しやすい
- 冪等性を作りやすい
- 差分比較がしやすい

---

## 7. データ保持ルール

### 7.1. セット数

- 1ドキュメントあたり最大20セットを想定
- UI 上も20セットを上限とする

### 7.2. 表示対象

画面表示時は以下のみ表示対象とする。

- ドキュメント `is_deleted = false`
- `sets[].is_deleted = false`

### 7.3. 総負荷量

`total_volume` は以下で算出する。

~~~text
sum(weight_kg * reps) for active sets
~~~

### 7.4. セット数

`set_count` は以下で算出する。

~~~text
active sets の件数
~~~

---

## 8. BigQuery へのマッピング方針

Firestore では 1ドキュメントに複数セットを保持するが、  
BigQuery `raw.training_log` では **1セット = 1レコード** として保存する。

### 8.1. マッピング表

| Firestore | BigQuery `raw.training_log` |
|---|---|
| `user_id` | `user_id` |
| `training_date` | `training_date` |
| `exercise_name` | `exercise_name` |
| `body_part_id` | `body_part` |
| `sets[n].set_id` | `log_id` |
| `sets[n].set_number` | `set_number` |
| `sets[n].weight_kg` | `weight_kg` |
| `sets[n].reps` | `reps` |
| `sets[n].rpe` | `rpe` |
| `sets[n].memo` | `memo` |
| `input_source` | `input_source` |
| `sets[n].created_at` | `created_at` |
| `sets[n].updated_at` | `updated_at` |
| `sets[n].is_deleted` | `is_deleted` |

### 8.2. `log_id` 方針

BigQuery 側の `log_id` には Firestore の `set_id` をそのまま使用する。

#### 理由

- Firestore 保存時点で一意性が保証できる
- 同期時の変換が単純
- BigQuery で upsert / dedupe しやすい
- set 単位の追跡がしやすい

---

## 9. クエリパターン

### 9.1. Input 画面: 当日・特定種目の復元

#### 条件

- `user_id`
- `training_date`
- `exercise_id`

#### 方法

- ドキュメントID直指定

#### 例

~~~text
training_logs/user_001_2026-04-12_bench_press
~~~

### 9.2. 特定日の全種目取得

#### 条件

- `user_id = X`
- `training_date = Y`
- `is_deleted = false`

#### 用途

- 将来の当日サマリー表示
- カレンダーやトップ画面への即時反映補助

### 9.3. 未同期ドキュメント取得

#### 条件

- `sync_status = pending`

#### 用途

- Firestore → BigQuery 同期バッチ

---

## 10. インデックス方針

### 10.1. 初期方針

初期フェーズでは、以下のシンプルなクエリに限定する。

- ドキュメントID直取得
- `where("user_id", "==", ...)`
- `where("training_date", "==", ...)`
- `where("sync_status", "==", ...)`

### 10.2. ねらい

- 複雑な複合インデックスを避ける
- 実装を単純に保つ
- 無駄な最適化をしない

### 10.3. 運用ルール

- まずはドキュメントID直取得を優先する
- 一覧取得は単純条件のみ
- 複雑な並び替えはアプリ側で対応する

---

## 11. 論理削除設計

### 11.1. ドキュメント全体削除

物理削除しない。  
以下を更新する。

~~~json
{
  "status": "deleted",
  "is_deleted": true,
  "sync_status": "pending"
}
~~~

### 11.2. セット単位削除

対象セットの `is_deleted` を `true` にする。

### 11.3. この方式を採用する理由

- 既存 BigQuery / dbt ロジックが論理削除前提
- 監査・調査がしやすい
- 同期時に差分扱いしやすい
- 誤操作時の復旧余地がある

---

## 12. 同期管理フィールド

### 12.1. `sync_status`

取りうる値:

- `pending`
- `synced`
- `failed`

### 12.2. `sync_version`

ドキュメント更新ごとに `+1` する。

### 12.3. `synced_at`

BigQuery 同期成功時刻を保持する。

### 12.4. 用途

- 再送制御
- 同期失敗調査
- 重複投入防止
- 同期状況の可視化

---

## 13. 編集制限

### 13.1. 現行仕様

- 作成から3時間以内のみ編集可能

### 13.2. Firestore での保持

以下のフィールドで表現する。

- `created_at`
- `editable_until`

### 13.3. UI 判定

~~~text
now < editable_until
~~~

### 13.4. 備考

将来的に「当日なら常に編集可」へ変更する場合も、  
このフィールド構成を維持したまま UI ロジックだけ変えられる。

---

## 14. バリデーションルール

Firestore 保存前にアプリ側で以下を検証する。

| 項目 | ルール |
|---|---|
| `training_date` | 必須。未来日付不可 |
| `weight_kg` | 0.0〜500.0 |
| `reps` | 1〜100 |
| `rpe` | `null` または 6.0〜10.0 |
| `memo` | 0〜200文字 |
| `set_number` | 1〜20 |
| `exercise_id` | 必須 |
| `body_part_id` | 必須 |

保存レイヤでも可能な範囲で再検証する。

---

## 15. 命名規則

### 15.1. コレクション名

~~~text
training_logs
~~~

### 15.2. ドキュメントID

~~~text
{user_id}_{training_date}_{exercise_id}
~~~

### 15.3. フィールド名

既存 BigQuery / dbt と揃えて **snake_case** を採用する。

例:

- `user_id`
- `training_date`
- `exercise_id`
- `body_part_id`
- `total_volume`

---

## 16. 将来拡張

### 16.1. サブコレクション化

将来、1ドキュメント内の `sets` 配列更新が扱いづらくなった場合は、以下へ移行可能とする。

~~~text
training_logs/{doc_id}/sets/{set_id}
~~~

ただし初期フェーズでは以下を優先して配列方式を採用する。

- 実装の簡単さ
- 読み取り回数削減
- Input 画面との相性

### 16.2. `draft` / `confirmed` 状態分離

必要になれば `status` に以下を追加可能。

- `draft`
- `confirmed`

ただし初期実装では以下で十分とする。

- `active`
- `deleted`

---

## 17. repository 層で想定する関数

Firestore SDK をページから直接呼ばず、util / repository に閉じ込める。

### 推奨関数

- `build_training_doc_id(user_id, training_date, exercise_id)`
- `get_training_log(user_id, training_date, exercise_id)`
- `save_training_log(...)`
- `soft_delete_set(user_id, training_date, exercise_id, set_id)`
- `soft_delete_training_log(user_id, training_date, exercise_id)`
- `list_training_logs_by_date(user_id, training_date)`
- `list_pending_sync_logs(limit=100)`
- `mark_synced(doc_id)`

---

## 18. 運用ルール

### 18.1. 保存

- 1種目分まとめて保存
- 保存時に `updated_at`, `last_edited_at`, `sync_status = "pending"` を更新
- `sync_version` をインクリメント

### 18.2. 削除

- セット削除は `sets[].is_deleted = true`
- 全削除はドキュメント `is_deleted = true`

### 18.3. 表示

- 表示時は `is_deleted = false` のみ対象
- `sets` は `is_deleted = false` のみ UI に出す

### 18.4. 同期

- `sync_status = "pending"` のドキュメントを同期対象とする
- BigQuery 同期成功後に `sync_status = "synced"` と `synced_at` を更新する

---

## 19. 設計上のメリット

この設計により、以下のメリットが得られる。

- 入力画面の復元が速い
- 1回の read で1種目分の入力状態を取れる
- BigQuery へ自然に展開できる
- 小規模アプリとして十分シンプル
- 既存 BigQuery / dbt 資産を活かせる

---

## 20. 注意事項

- Firestore は一次保存先とし、分析用途には使いすぎない
- 集計・ランキング・履歴分析は引き続き BigQuery を使う
- Firestore と BigQuery の一時的不整合は許容し、BigQuery は非同期反映とする
- 物理削除は原則行わない

---

## 21. 最終方針

初期実装では、以下を正式採用とする。

- コレクション: `training_logs`
- 単位: `1ユーザー × 1日 × 1種目`
- ID: `{user_id}_{training_date}_{exercise_id}`
- セット保持: `sets` 配列
- 削除: 論理削除
- 同期: `sync_status` ベースで日次同期

この設計をベースに、まずは Input 画面を Firestore 化する。
