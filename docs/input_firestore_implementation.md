# Input画面 Firestore 化 実装指示書
更新日: 2026-04-12

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

---

## 4. 今回やらないこと

以下は今回のスコープ外とする。

- `Calendar.py` の Firestore 化
- `Dashboard.py` の Firestore 化
- `Ranking.py` の Firestore 化
- `Social.py` の Firestore 化
- Firestore → BigQuery 同期処理
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

---

## 10. 実装完了後に出してほしい内容

実装完了後は以下をまとめること。

1. 変更ファイル一覧
2. 変更内容要約
3. 追加した関数一覧
4. Firestore ドキュメント構造の最終版
5. 残課題
