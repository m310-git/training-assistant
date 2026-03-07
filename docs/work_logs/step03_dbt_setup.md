# Step 3: dbt Coreセットアップ

## 概要

dbt Coreをインストールし、BigQueryとの接続を設定・確認する。

## 前提条件

- [ ] Step 2 完了
- [ ] Python 3.10以上 インストール済み
- [ ] secrets/sa-dbt-runner.json が存在する

---

## 手順

### 3-1. Python仮想環境の作成

    # プロジェクトルートで実行
    python -m venv venv

    # 有効化（Windows Git Bash）
    source venv/Scripts/activate

    # 有効化（Mac/Linux）
    source venv/bin/activate

    # 確認
    which python
    python --version

### 3-2. dbt Coreインストール

    pip install dbt-bigquery

    # 確認
    dbt --version

期待結果:

    Core:
      - installed: 1.x.x

    Plugins:
      - bigquery: 1.x.x

### 3-3. dbtプロジェクト初期化

    cd dbt

    dbt init training_assistant

    # 対話形式で以下を選択:
    # - Which database would you like to use? → bigquery
    # - authentication method → service_account
    # - keyfile → ../secrets/sa-dbt-runner.json
    # - project → training-assistant-prod
    # - dataset → staging
    # - threads → 1
    # - job_execution_timeout_seconds → 300
    # - location → asia-northeast1

※ dbt init で生成されたファイルを dbt/ 直下に移動して整理する

### 3-4. dbt_project.yml の編集

dbt/dbt_project.yml を以下の内容に編集:

    name: 'training_assistant'
    version: '1.0.0'
    config-version: 2

    profile: 'training_assistant'

    model-paths: ["models"]
    analysis-paths: ["analyses"]
    test-paths: ["tests"]
    seed-paths: ["seeds"]
    macro-paths: ["macros"]
    snapshot-paths: ["snapshots"]

    target-path: "target"
    clean-targets:
      - "target"
      - "dbt_packages"

    models:
      training_assistant:
        staging:
          +materialized: incremental
          +schema: staging
        mart:
          +materialized: table
          +schema: mart

### 3-5. profiles.yml の作成

~/.dbt/profiles.yml を作成（またはプロジェクトルートに配置）:

    training_assistant:
      outputs:
        dev:
          type: bigquery
          method: service-account
          project: training-assistant-prod
          dataset: staging
          threads: 1
          keyfile: /absolute/path/to/secrets/sa-dbt-runner.json
          job_execution_timeout_seconds: 300
          location: asia-northeast1
      target: dev

※ keyfile のパスは絶対パスで指定すること
※ profiles.yml は .gitignore で除外済み

### 3-6. ソース定義の作成

dbt/models/staging/sources.yml を作成:

    version: 2

    sources:
      - name: raw
        database: training-assistant-prod
        schema: raw
        tables:
          - name: training_log
            description: "生トレーニングログ。1セット=1レコード。"
          - name: exercise_master
            description: "種目マスタ。"
          - name: user_master
            description: "ユーザーマスタ。"
          - name: exercise_request
            description: "種目追加リクエスト。"
          - name: notification_log
            description: "通知送信ログ。"

### 3-7. 接続確認

    cd dbt
    dbt debug

期待結果（全てPASSすること）:

    Connection:
      ...
      Connection test: [OK connection ok]

    All checks passed!

### 3-8. 空実行テスト

    dbt run --select staging

期待結果:

    Completed with 0 errors and 0 warnings.

※ まだモデルがないので0件だが、エラーなく完了すればOK

### 3-9. requirements.txt の作成

プロジェクトルートに作成:

    cat << 'EOF' > requirements.txt
    dbt-bigquery>=1.7,<2.0
    streamlit>=1.30,<2.0
    google-cloud-bigquery>=3.0,<4.0
    pandas>=2.0,<3.0
    plotly>=5.0,<6.0
    line-bot-sdk>=3.0,<4.0
    EOF

### 3-10. Gitコミット＆プッシュ

    git add dbt/dbt_project.yml dbt/models/staging/sources.yml requirements.txt docs/work_logs/
    git commit -m "feat: dbt Core setup with BigQuery connection"
    git push origin main

※ profiles.yml と secrets/ はpushしないこと

---

## 現在のdbt構成

    dbt/
    ├── dbt_project.yml
    ├── models/
    │   ├── staging/
    │   │   └── sources.yml
    │   └── mart/
    ├── seeds/
    ├── tests/
    └── macros/

---

## 完了チェックリスト

- [ ] Python仮想環境が作成・有効化されている
- [ ] dbt-bigquery がインストールされている
- [ ] dbt_project.yml が設定されている
- [ ] profiles.yml が作成されている（Git管理外）
- [ ] sources.yml でraw層5テーブルが定義されている
- [ ] dbt debug が全てPASS
- [ ] requirements.txt が作成されている
- [ ] profiles.yml が .gitignore で除外されている
