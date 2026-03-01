# データ駆動型トレーニングアシスタント

## 概要
主要複合種目（BIG3）の7日間移動平均トレーニングボリュームを継続的に向上させるためのデータ駆動型アシスタント。

## KPI
- 7日間移動平均トレーニングボリューム（重量×回数×セット数）の週次変化率 ≧ 1.0%

## 技術スタック（MVP）
| コンポーネント | 技術 |
|---|---|
| DWH | Google BigQuery |
| 変換 | dbt Core |
| 入力/可視化 | Streamlit Cloud |
| 通知ロジック | Cloud Functions (2nd gen) |
| スケジューラ | Cloud Scheduler |
| 通知サービス | LINE Messaging API |
| シークレット管理 | GCP Secret Manager |

## フェーズ計画
| Phase | スコープ | 状態 |
|---|---|---|
| 1 (MVP) | 入力・変換・可視化・通知の最小構成 | 🔧 構築中 |
| 2 (品質) | Great Expectations導入 | ⏳ 未着手 |
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

## セットアップ
詳細は `docs/design.md` を参照。
## セキュリティ
- 認証情報は GCP Secret Manager で管理
- サービスアカウントは最小権限の原則で設定
- `.gitignore` で機密ファイルを除外
