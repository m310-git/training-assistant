# Step 0: Git・リポジトリセットアップ
## 概要
GitHubにプライベートリポジトリを作成し、プロジェクトのディレクトリ構成と設定ファイルを整備する。
## 前提条件
- [ ] GitHubアカウント作成済み
- [ ] Git インストール済み
- [ ] GitHub CLI（gh）インストール済み

# **実施した作業の全体像**

```
1. リポジトリ作成
2. ディレクトリ構造作成
3. 設定ファイル作成
4. 初回コミット＆プッシュ
5. developブランチ作成
```
---



## 手順
### 0-1. リポジトリ作成
    gh repo create training-assistant \
        --private \
        --description "データ駆動型トレーニングアシスタント" \
        --clone
    cd training-assistant
### 0-2. ディレクトリ構成作成
    mkdir -p streamlit/{pages,utils,.streamlit}
    mkdir -p dbt/{models/{staging,mart},seeds,tests,macros}
    mkdir -p cloud_functions/{dbt_runner,notifier}
    mkdir -p scripts
    mkdir -p secrets
    mkdir -p docs/work_logs
    mkdir -p .github/{workflows,ISSUE_TEMPLATE}
    mkdir -p tests/{integration,unit}
作成されるディレクトリ構成:
```
    training-assistant/
    ├── .github/
    │   ├── ISSUE_TEMPLATE/
    │   └── workflows/
    ├── cloud_functions/
    │   ├── dbt_runner/
    │   └── notifier/
    ├── dbt/
    │   ├── macros/
    │   ├── models/
    │   │   ├── mart/
    │   │   └── staging/
    │   ├── seeds/
    │   └── tests/
    ├── docs/
    │   └── work_logs/
    ├── scripts/
    ├── secrets/
    ├── streamlit/
    │   ├── .streamlit/
    │   ├── pages/
    │   └── utils/
    └── tests/
        ├── integration/
        └── unit/
```

### 0-3. .gitignore 作成
    cat << 'EOF' > .gitignore
    # セキュリティ最重要
    secrets/
    *.json
    !dbt/dbt_project.yml
    !dbt/packages.yml
    .streamlit/secrets.toml
    profiles.yml
    .env
    .env.*
    !.env.example
    # ビルド成果物
    __pycache__/
    *.py[cod]
    venv/
    .venv/
    dbt/target/
    dbt/dbt_packages/
    dbt/logs/
    # IDE
    .vscode/
    .idea/
    .DS_Store
    Thumbs.db
    # テスト
    .coverage
    htmlcov/
    .pytest_cache/
    EOF
### 0-4. .env.example 作成
    cat << 'EOF' > .env.example
    # GCP
    GCP_PROJECT_ID=training-assistant-prod
    GCP_REGION=asia-northeast1
    # BigQuery
    BQ_DATASET_RAW=raw
    BQ_DATASET_STAGING=staging
    BQ_DATASET_MART=mart
    # LINE Messaging API
    LINE_CHANNEL_ACCESS_TOKEN=your_token_here
    LINE_CHANNEL_SECRET=your_secret_here
    # Streamlit
    STREAMLIT_PASSWORD=your_password_here
    EOF
### 0-5. README.md 作成
    cat << 'EOF' > README.md
    # データ駆動型トレーニングアシスタント
    ## 概要
    3名のトレーニング仲間向けのデータ駆動型トレーニング記録・分析アプリケーション。
    ## ドキュメント
    - [設計書](docs/design_document.md)
    - [データ定義書](docs/data_dictionary.md)
    - [作業ログ](docs/work_logs/README.md)
    ## 技術スタック
    - **DWH**: Google BigQuery
    - **変換**: dbt Core
    - **入力/可視化**: Streamlit Cloud
    - **通知**: Cloud Functions + LINE Messaging API
    - **スケジューラ**: Cloud Scheduler
    - **ML**: BigQuery ML
    ## フェーズ計画
    | Phase | スコープ | 期間目安 |
    |---|---|---|
    | Phase 1 (MVP) | 入力・変換・可視化・通知・ランキング・ML提案 | 3〜4週間 |
    | Phase 2 (品質) | dbt-expectations + Elementary | 1〜2週間 |
    | Phase 3 (自動化) | Prefect Cloud | 1週間 |
    | Phase 4 (IaC) | Terraform | 1週間 |
    EOF
### 0-6. 初回コミット＆プッシュ
    git add .
    git commit -m "chore: initial project structure and configuration"
    git push -u origin main

### 0-7. developブランチ作成

```bash
# developブランチを作成して切り替え
git checkout -b develop

# GitHubにプッシュ
git push -u origin develop
```

**ブランチ運用：**

```
main     → 本番。常に動く状態を保つ
develop  → 開発統合。テスト通過後にmainへマージ
feature/ → 各機能開発。developから分岐→developへマージ
```
---
## 完了チェックリスト
- [ ] GitHubにプライベートリポジトリが作成されている
- [ ] ディレクトリ構成が設計書と一致している
- [ ] .gitignore で secrets/ が除外されている
- [ ] mainブランチにpush済み
