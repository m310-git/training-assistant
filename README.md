# データ駆動型トレーニングアシスタント

## 概要
主要複合種目（BIG3）の7日間移動平均トレーニングボリュームを継続的に向上させるためのデータ駆動型アシスタント。

## アプリケーション
https://training-assistant-m310.streamlit.app/

## KPI
- 7日間移動平均トレーニングボリューム（重量×回数×セット数）の週次変化率 ≧ 1.0%

## 技術スタック（MVP）
| コンポーネント | 技術 |
|---|---|
| DWH | Google BigQuery |
| 入力データストア | Google Firestore |
| 変換 | dbt Core |
| 入力/可視化 | Streamlit Cloud |
| 通知ロジック | Cloud Functions (2nd gen) |
| スケジューラ | Cloud Scheduler |
| 通知サービス | LINE Messaging API |
| シークレット管理 | GCP Secret Manager |
| ML | BigQuery ML |

## フェーズ計画
| Phase | スコープ | 状態 |
|---|---|---|
| 1 (MVP) | 入力・変換・可視化・通知の最小構成 | ✅ 完了 |
| 2 (品質) | dbt-expectations + Elementary導入 | ⏳ 未着手 |
| 3 (自動化) | Prefect Cloud導入 | ⏳ 未着手 |
| 4 (IaC) | Terraform導入 | ⏳ 未着手 |

## ディレクトリ構造
training-assistant/
├── streamlit/          # 入力UI・ダッシュボード
├── dbt/                # データ変換モデル
├── cloud_functions/    # 通知・dbt実行
├── scripts/            # セットアップスクリプト
├── tests/              # テストコード
├── docs/               # 設計書
└── .github/workflows/  # CI/CD

## 機能一覧

### Streamlit アプリケーション
- **トレーニング入力（Input）**: セット単位の入力、自動保存、当日復元、編集制限（3時間）、休憩タイマー、過去実績表示、BigQuery ML提案
- **カレンダー（Calendar）**: 月間カレンダー、部位表示、詳細表示、編集ボタン
- **ダッシュボード（Dashboard）**: KPI表示、進捗曲線、最終トレーニング日
- **ランキング（Ranking）**: 週間・月間・全期間ランキング、部位別ランキング
- **ソーシャル（Social）**: 他ユーザーの記録閲覧、記録更新フィード
- **種目追加リクエスト（ExerciseRequest）**: 種目追加リクエスト送信、リクエスト状況確認
- **管理者画面（Admin）**: 種目承認/却下、種目マスタ管理、種目の手動追加、種目の無効化

### Firestore 移行
- Input画面の保存先をBigQueryからFirestoreに変更
- Firestore → BigQuery 同期処理を実装
- 入力画面の体感速度を改善

### BigQuery ML
- トレーニング提案機能（重量・回数予測）
- 過去実績に基づく提案

## セットアップ
詳細は `docs/design.md` を参照。

## デプロイ

### Streamlit Cloud
1. Streamlit Cloudにリポジトリを接続
2. `.streamlit/secrets.toml` にシークレット情報を設定
3. デプロイ

### Cloud Functions
```bash
cd cloud_functions/dbt_runner
gcloud functions deploy handle_daily_pipeline \
  --runtime python311 \
  --trigger-http \
  --allow-unauthenticated \
  --memory 1024MB \
  --timeout 540s \
  --entry-point handle_daily_pipeline
```

### Cloud Scheduler
```bash
gcloud scheduler jobs create http daily-pipeline \
  --schedule "0 21 * * *" \
  --time-zone Asia/Tokyo \
  --uri <Cloud Functions URL> \
  --http-method POST
```
## セキュリティ
- 認証情報は GCP Secret Manager で管理
- サービスアカウントは最小権限の原則で設定
- `.gitignore` で機密ファイルを除外
