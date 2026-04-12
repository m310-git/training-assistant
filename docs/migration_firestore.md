# Firestore 移行方針書
更新日: 2026-04-12

## 1. 目的

現状の Streamlit アプリは、ユーザー入力のたびにスクリプト全体が再実行され、
そのたびに BigQuery へ複数回クエリを発行しているため、入力体験が重い。

特に `streamlit/pages/1_📝_Input.py` は、
- 部位一覧取得
- 種目一覧取得
- 過去履歴取得
- 提案取得
- 当日既存記録取得
- 再取得
などを1ページ内で繰り返しており、Streamlit の rerun モデルと相性が悪い。

そのため、**入力・編集のリアルタイム処理を Firestore に移し、BigQuery は分析・集計専用に寄せる**。

---

## 2. 目標

### 2.1. 主目標
- 入力画面の体感速度を改善する
- 保存・復元・編集のレスポンスを改善する
- BigQuery をインタラクティブ入力用途から切り離す
- 既存の dbt / mart / ランキング / ダッシュボードを極力活かす

### 2.2. 非目標
- 初回フェーズでは全画面を Firestore 化しない
- ランキング、ダッシュボード、ソーシャル、カレンダーの集計ロジックは原則 BigQuery のまま
- BigQuery ML / dbt モデル構造は初回では大きく変更しない

---

## 3. 採用アーキテクチャ

### 3.1. 役割分担
- **Firestore**
  - 入力中データ
  - 当日編集データ
  - セット単位の保存
  - 当日復元
  - 論理削除管理
- **BigQuery**
  - 日次集計
  - ランキング
  - ダッシュボード
  - カレンダー
  - ソーシャル
  - ML提案
- **dbt**
  - staging / mart モデル生成
- **Cloud Scheduler + Cloud Run functions**
  - Firestore → BigQuery 同期
  - dbt 実行
  - 通知

### 3.2. 設計意図
Firestore は小規模な読み書きに向いており、無料枠として
1 GiB 保存、50,000 reads/日、20,000 writes/日、20,000 deletes/日がある。
一方 BigQuery は 1 TiB/月のクエリ無料枠と 10 GiB/月のストレージ無料枠があり、
分析・集計用途と相性が良い。BigQuery への **batch loading は無料**であり、
入力系は Firestore、分析系は BigQuery に分離する構成が無料枠とUXの両面で相性が良い。 ([docs.cloud.google.com](https://docs.cloud.google.com/firestore/quotas?utm_source=openai))

---

## 4. 移行スコープ

### 4.1. フェーズ1（今回）
対象:
- `streamlit/pages/1_📝_Input.py`

変更内容:
- セット入力の保存先を BigQuery から Firestore に変更
- 当日復元を Firestore から取得
- 当日編集も Firestore ベースに変更
- `st.form` を導入し、入力中の rerun を減らす
- BigQuery は履歴参照・提案表示のみに限定

### 4.2. フェーズ2
対象:
- Cloud Function / Cloud Run function
- BigQuery raw 取り込み処理

変更内容:
- Firestore の確定済みトレーニングデータを BigQuery `raw.training_log` に同期
- dbt を実行し mart を更新
- 既存のカレンダー / ダッシュボード / ランキングを継続利用

### 4.3. フェーズ3（必要なら）
対象:
- `app.py`
- `Calendar.py`
- `Social.py`

変更内容:
- 「当日だけ即時反映が必要」な一部参照を Firestore 補助参照に変更
- 集計用途は引き続き BigQuery

---

## 5. データフロー

### 5.1. 入力時
1. ユーザーが Streamlit の Input 画面で入力
2. Firestore の `training_logs` に保存
3. 画面は Firestore から即時再読込または session_state 更新
4. BigQuery には即時書き込みしない

### 5.2. 日次同期時
1. Scheduler が同期ジョブを起動
2. Firestore から BigQuery raw 用データを抽出
3. BigQuery `raw.training_log` に batch load / まとめ書き
4. dbt run / dbt test 実行
5. mart 更新

### 5.3. 参照時
- Input 画面の当日入力・復元: Firestore
- 過去履歴・提案・ランキング・ダッシュボード: BigQuery / mart

---

## 6. Firestore に移す理由

### 6.1. パフォーマンス
現状は Streamlit rerun により、入力のたびに BigQuery クエリが複数回発生する。
Firestore による単純な document read/write にすることで、
入力画面の待ち時間を大幅に減らせる。

### 6.2. コスト
BigQuery は batch loading が無料だが、ストリーミング系の取り込みは別料金体系であり、
インタラクティブ入力の主保存先としては不向き。
Firestore へ一旦保存し、BigQuery へは日次同期とする方が無料枠運用に向く。 ([cloud.google.com](https://cloud.google.com/bigquery/pricing.html?utm_source=openai))

### 6.3. 保守性
入力系の CRUD と分析系の集計を分離することで、
コード責務が明確になる。

---

## 7. BigQuery 連携方針

### 7.1. BigQuery raw テーブルは維持
既存の `raw.training_log` は維持する。
ただし、直接 Streamlit から insert しない。

### 7.2. 同期方式
初期案:
- 日次バッチ同期

将来的な拡張案:
- 5〜15分ごとのマイクロバッチ
- 明示的な「確定」操作時のみ同期

### 7.3. 同期単位
Firestore 上の「1種目1日単位」ドキュメントを展開し、
BigQuery では従来通り「1セット1レコード」で保存する。

---

## 8. 論理削除方針

Firestore 上では以下のどちらかで対応する:
- セット単位に `is_deleted = true` を持たせる
- 削除済みセットを配列から取り除くが、監査用に `deleted_sets` に移す

初期実装では、BigQuery との整合性維持のため、
**セット単位に `is_deleted` を保持する方式**を採用する。

理由:
- 既存 BigQuery / dbt ロジックが論理削除前提
- 同期時に raw.training_log へ自然にマッピングできる

---

## 9. 既存コード変更方針

### 9.1. 追加ファイル
- `streamlit/utils/firestore_client.py`
- `streamlit/repositories/training_firestore_repository.py`（任意）
- `docs/firestore_collection_design.md`

### 9.2. 主変更ファイル
- `streamlit/pages/1_📝_Input.py`

### 9.3. 基本ルール
- ページに生SQLを増やさない
- Firestore アクセスは util / repository に閉じ込める
- Streamlit UI とデータアクセス層を分離する
- 保存は `st.form_submit_button()` ベースに寄せる

---

## 10. セキュリティ方針

### 10.1. Firestore 認証
Streamlit サーバー側から Firestore へアクセスするため、
GCP サービスアカウントを使用する。

### 10.2. 秘密情報
認証情報は `st.secrets` 経由で管理する。
コードにキーをハードコードしない。

### 10.3. 権限
サービスアカウントには最小権限を付与する。
必要な権限は原則:
- Firestore 読み書き
- BigQuery 読み取り/書き込み（同期ジョブ側）
- Secret 参照（必要時のみ）

---

## 11. 無料枠・課金注意点

### 11.1. Firestore
Firestore は 1プロジェクトにつき無料DBは1つ。
無料枠を超えると課金対象になる。
また TTL deletes / PITR / Backup / Restore / Clone は無料枠に含まれない。 ([docs.cloud.google.com](https://docs.cloud.google.com/firestore/quotas?utm_source=openai))

### 11.2. BigQuery
BigQuery は Free Program で 1 TiB/月のクエリ無料枠と 10 GiB/月の保存無料枠がある。
ただし無料枠を超えるクエリ・保存は課金対象となる。Batch load は無料。 ([docs.cloud.google.com](https://docs.cloud.google.com/free/docs/measure-compare-performance?utm_source=openai))

### 11.3. Scheduler / Functions
Cloud Scheduler は billing account あたり3 jobsまで無料。
Cloud Run functions は月 200万 invocations の無料枠がある。 ([cloud.google.com](https://cloud.google.com/scheduler/pricing?utm_source=openai))

---

## 12. リスクと対策

### リスク1: Firestore と BigQuery の一時的不整合
対策:
- Firestore を一次ソースオブトゥルースとする
- BigQuery は分析用の非同期反映と明示
- UI 上で「分析反映は日次更新」と説明

### リスク2: 同期処理の重複投入
対策:
- Firestore ドキュメントに `sync_status`, `synced_at`, `sync_version` を持つ
- BigQuery 側は idempotent な upsert または論理削除＋再生成で扱う

### リスク3: Firestore 配列更新の競合
対策:
- 配列丸ごと更新ではなく、保存時にサーバー側で正規化
- 必要なら将来サブコレクション方式へ移行できるよう ID 設計を固定する

---

## 13. 実装順序

### Step 1
- Firestore client utility を追加
- ローカル / Streamlit Cloud で接続確認

### Step 2
- Input 画面を `st.form` 化
- Firestore 保存・復元に切り替え

### Step 3
- 既存 BigQuery 直書き処理を feature flag で切り替え可能にする

### Step 4
- Firestore → BigQuery 同期 function を実装

### Step 5
- dbt 連携を既存 daily pipeline に統合

---

## 14. 完了条件

- Input 画面で BigQuery 直書きなしに保存・復元・編集ができる
- 当日入力の体感速度が改善している
- 日次同期で BigQuery raw.training_log に正しく反映される
- 既存ランキング / ダッシュボードが壊れていない

---

## 15. 備考

本移行は「入力系だけ Firestore に逃がし、分析系は BigQuery を活かす」方針であり、
全置換ではない。
小規模構成・無料枠重視・既存資産活用のバランスを優先する。
