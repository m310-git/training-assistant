# 設計書：データ駆動型トレーニングアシスタント

※ 詳細な設計書は別途管理。ここには概要を記載。

## アーキテクチャ
BigQueryを核としたデータレイクハウス戦略（raw → staging → mart の3層構造）

## データフロー
1. データ入力: Streamlit → BigQuery raw
2. データ変換: Cloud Scheduler → Cloud Functions → dbt → BigQuery staging/mart
3. 日次通知: Cloud Scheduler → Cloud Functions → LINE
4. 開始通知: Streamlit → Cloud Functions → LINE
5. 可視化: Streamlit → BigQuery mart → グラフ表示
