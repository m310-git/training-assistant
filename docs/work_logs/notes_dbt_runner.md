# 補足: dbt-runner の運用方針

## 背景

Step 7でCloud Functions（dbt-runner）をデプロイしたが、
Cloud Functions内でdbt CLIをsubprocess実行する方式は
プロジェクトファイルのバンドル問題により動作しなかった。

## 暫定対応（Phase 1 MVP期間）

dbt runはローカルで手動実行する。

    cd dbt
    dbt run
    dbt test

### 実行タイミング

| タイミング | 頻度 | 内容 |
|---|---|---|
| 毎朝（目安 06:00） | 日次 | dbt run + dbt test |
| データ入力後すぐ反映したい時 | 随時 | dbt run |

### dbt runをしないとどうなるか

- Streamlitで入力したデータはraw層に保存される（即時）
- ただしダッシュボード・ランキング・カレンダー等のmart層には反映されない
- dbt runを実行して初めてmart層が更新される

## 本対応（Phase 3）

Phase 3でPrefect Cloudを導入し、dbt runを自動化する。

    Phase 3 計画:
    - Prefect Cloud（無料枠）でワークフロー管理
    - Cloud Schedulerを置換
    - dbt run + dbt test + 通知判定を1つのFlowに統合

## Cloud Schedulerへの影響

現在のCloud Scheduler 3ジョブはそのまま維持:

| ジョブ | 対象 | 状態 |
|---|---|---|
| daily-pipeline | dbt-runner（Cloud Functions） | ❌ 動作しない（暫定でローカル実行） |
| weekly-ranking | notifier-weekly-ranking | ✅ 正常動作 |
| monthly-ranking | notifier-monthly-ranking | ✅ 正常動作 |

daily-pipelineジョブは無効化してもよいが、
Phase 3で置き換えるため残しておく。

## sa-cf-notifier 権限変更の記録

notification_logへの書き込みにdataEditor権限が必要だったため変更:

    変更前: roles/bigquery.dataViewer + roles/bigquery.jobUser
    変更後: roles/bigquery.dataEditor + roles/bigquery.jobUser

    実行したコマンド:
    gcloud projects add-iam-policy-binding training-assistant-prod \
        --member="serviceAccount:sa-cf-notifier@training-assistant-prod.iam.gserviceaccount.com" \
        --role="roles/bigquery.dataEditor"
