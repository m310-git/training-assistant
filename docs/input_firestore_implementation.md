# Input画面 Firestore 化 実装指示書
更新日: 2026-04-16

## 1. 目的

`streamlit/pages/1_📝_Input.py` の入力・保存・復元・削除処理を  
BigQuery 直結から Firestore ベースに移行し、入力画面の体感速度を改善する。

---

## 2. 今回の実装対象

### 対象ファイル

- `streamlit/pages/1_📝_Input.py`
- `streamlit/utils/firestore_client.py`（新規作成）
- `requirements.txt`

### 参照ファイル

- `streamlit/utils/bigquery_client.py`
- `streamlit/utils/auth.py`
- `streamlit/utils/validators.py`
- `docs/migration_firestore.md`
- `docs/firestore_collection_design.md`

---

## 3. 今回やること

### 3.1. Firestore util の追加

`streamlit/utils/firestore_client.py` を新規作成し、以下の責務を持たせる。

- Firestore client 初期化
- ドキュメントID生成
- 1種目1日分の取得
- 1種目1日分の保存
- セット単位論理削除
- ドキュメント全体論理削除

### 3.2. Input 画面の保存先切替

`streamlit/pages/1_📝_Input.py` の以下を Firestore ベースへ変更する。

- 当日の既存記録取得
- 保存
- 末尾削除
- 全削除
- 当日復元

### 3.3. UI 改善

セット入力部分を `st.form` に変更し、入力のたびの rerun を減らす。

### 3.4. 不要処理の削除

以下を削除する。

- `time.sleep(2)`
- BigQuery 再読込のための retry ロジック
- Input画面内の BigQuery 直書き保存ロジック

### 3.5. Firestore → BigQuery 同期処理

`cloud_functions/dbt_runner/main.py` に Firestore → BigQuery 同期処理を追加する。

- Firestore から `sync_status = "pending"` のドキュメントを取得
- ドキュメントの `sets` 配列を展開して BigQuery `raw.training_log` に streaming insert
- 同期成功後に Firestore ドキュメントの `sync_status = "synced"` に更新
- `synced_at` に現在時刻を設定

---

## 4. 今回やらないこと

以下は今回のスコープ外とする。

- `Calendar.py` の Firestore 化
- `Dashboard.py` の Firestore 化
- `Ranking.py` の Firestore 化
- `Social.py` の Firestore 化
- dbt モデル変更
- BigQuery テーブル定義変更
- auth 全面改修

---

## 5. BigQuery に残すもの

以下の参照は従来どおり BigQuery から取得する。

- 部位一覧
- 種目一覧
- 過去履歴
- ML提案
- 直近3回実績

---

## 6. 実装方針

### 6.1. 種目選択

現在の `exercise_name` ベース選択を、可能な限り `exercise_id` ベースへ寄せる。

### 6.2. Firestore ドキュメント単位

1ドキュメント = `1ユーザー × 1日 × 1種目`

ドキュメントID形式:

~~~text
{user_id}_{training_date}_{exercise_id}
~~~

### 6.3. セット保持

- `sets` 配列で保持する
- 各セットに `set_id` を持たせる
- `set_id` は UUID を使用する
- BigQuery 側の `log_id` と互換になるようにする

### 6.4. 削除

- 物理削除しない
- セット削除は `sets[].is_deleted = true`
- 全削除はドキュメント `is_deleted = true`

### 6.5. 同期用フィールド

以下を保持する。

- `sync_status`
- `sync_version`
- `synced_at`

今回は同期処理自体は作らないが、後続実装のためにフィールドは入れる。

---

## 7. 実装時の制約

- Firestore SDK をページ内に直接書かない
- Firestore アクセスは `streamlit/utils/firestore_client.py` に閉じ込める
- BigQuery 参照ロジックは極力壊さない
- 既存 UI を大きく崩さない
- コメントは日本語で書く
- セキュリティ情報をコードにハードコードしない

---

## 8. 推奨実装順序

1. `requirements.txt` に Firestore 依存追加
2. `streamlit/utils/firestore_client.py` 新規作成
3. Firestore client 初期化確認
4. `Input.py` の種目選択を `exercise_id` ベースへ整理
5. 当日復元を Firestore へ変更
6. 保存を Firestore へ変更
7. 末尾削除 / 全削除を Firestore へ変更
8. セット入力を `st.form` 化
9. 不要な `sleep / retry` ロジック削除
10. 動作確認

---

## 9. 完了条件

以下を満たしたら完了とする。

- Input画面で BigQuery 直書きなしに保存できる
- 保存後に Firestore から復元できる
- 末尾削除が動く
- 全削除が動く
- `st.form` 化されている
- `time.sleep(2)` が削除されている
- BigQuery の履歴・提案・直近実績表示が壊れていない
- Firestore → BigQuery 同期処理が実装されている
- Firestore → BigQuery 同期の実データE2E確認が完了している
- `synced_at` のルール修正が実装されている（未同期状態に戻すときsynced_atもnullに戻す）

---

## 10. 実装完了後に出してほしい内容

実装完了後は以下をまとめること。

1. 変更ファイル一覧
2. 変更内容要約
3. 追加した関数一覧
4. Firestore ドキュメント構造の最終版
5. 残課題

---

## 11. 実装完了内容

### 11.1. 変更ファイル一覧

- `streamlit/utils/firestore_client.py`（新規作成）
- `streamlit/pages/1_📝_Input.py`（変更）
- `cloud_functions/dbt_runner/main.py`（変更）
- `cloud_functions/dbt_runner/requirements.txt`（変更）

### 11.2. 変更内容要約

**Streamlit 側**:
- Firestore クライアントユーティリティを新規作成
- Input 画面の保存先を BigQuery から Firestore に変更
- セット入力を `st.form` 化
- 不要な `sleep / retry` ロジックを削除
- `synced_at` のルール修正（未同期状態に戻すときsynced_atもnullに戻す）

**Cloud Functions 側**:
- Firestore → BigQuery 同期処理を実装
- IAM 権限付与（`roles/datastore.user`）
- メモリを 512MB から 1024MB に増加

### 11.3. 追加した関数一覧

**`streamlit/utils/firestore_client.py`**:
- `get_firestore_client()`: Firestore クライアント初期化
- `build_training_doc_id()`: ドキュメントID生成
- `get_training_log()`: トレーニングログ取得
- `save_training_log()`: トレーニングログ保存
- `soft_delete_set()`: セット単位論理削除
- `soft_delete_training_log()`: ドキュメント全体論理削除

**`cloud_functions/dbt_runner/main.py`**:
- `sync_firestore_to_bigquery()`: Firestore → BigQuery 同期処理

### 11.4. Firestore ドキュメント構造の最終版

```json
{
  "doc_id": "{user_id}_{training_date}_{exercise_id}",
  "user_id": "user_001",
  "user_name": "ユーザー名",
  "training_date": "2026-04-16",
  "body_part_id": "chest",
  "body_part_name": "胸",
  "exercise_id": "bench_press",
  "exercise_name": "ベンチプレス",
  "input_source": "streamlit",
  "status": "active",
  "is_deleted": false,
  "sets": [
    {
      "set_id": "UUIDv4",
      "set_number": 1,
      "weight_kg": 100.0,
      "reps": 5,
      "rpe": 8.0,
      "memo": "",
      "is_deleted": false,
      "created_at": "ISO8601",
      "updated_at": "ISO8601"
    }
  ],
  "set_count": 3,
  "total_volume": 1500.0,
  "created_at": "ISO8601",
  "updated_at": "ISO8601",
  "last_edited_at": "ISO8601",
  "editable_until": "ISO8601",
  "sync_status": "pending" | "synced",
  "synced_at": "ISO8601" | null,
  "sync_version": 1,
  "schema_version": 1
}
```

### 11.5. synced_at のルール

**保存時**:
- 新規作成: `sync_status = "pending"`, `synced_at = null`
- 更新: `sync_status = "pending"`, `synced_at = null`
- セット削除: `sync_status = "pending"`, `synced_at = null`
- 全体削除: `sync_status = "pending"`, `synced_at = null`

**同期成功時**:
- `sync_status = "synced"`, `synced_at = 現在時刻`（Cloud Function 側で設定）

### 11.6. 残課題

- Firestore filter 警告（主因ではないため無視可能）
- メモリ増加（1024MB、無料枠内に収まる可能性が高い）
- Firestore filter の位置引数をキーワード引数に修正することで解消可能
