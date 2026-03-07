# Step 1: GCP基盤セットアップ

## 概要

GCPプロジェクトの作成、サービスアカウント・API有効化・LINE Messaging API・Secret Managerの設定を行う。

## 前提条件

- [ ] Step 0 完了
- [ ] Googleアカウント作成済み
- [ ] gcloud CLI インストール済み

# **実施した作業の全体像**

```
1. gcloud CLI インストール
2. GCP初期設定（ログイン・利用規約同意）
3. プロジェクト作成
4. リージョン設定
5. 課金アカウントリンク
6. API有効化
7. サービスアカウント作成（3つ）
8. サービスアカウントキー生成
9. LINE Messaging API チャネル作成
10. Secret Manager にAPIキー格納
11. 予算アラート設定
```

---

## 手順

### 1-1. gcloud CLI インストール確認

    gcloud version

Google Cloud SDK 4xx.x.x が表示されればOK。
未インストールの場合: https://cloud.google.com/sdk/docs/install?hl=ja

### 1-2. GCPログイン＆初期設定

    gcloud init

対話形式で以下を実施:
- Googleアカウントでログイン（ブラウザ認証）
- 利用規約に同意（初回のみ）

※「Callers must accept Terms of Service」エラーが出た場合:
→ https://console.cloud.google.com/ にアクセスして利用規約に同意 → 再実行

### 1-3. プロジェクト作成

    gcloud projects create training-assistant-prod --name="Training Assistant"

    # デフォルトプロジェクトに設定
    gcloud config set project training-assistant-prod

    # 確認
    gcloud projects list

| 項目 | 値 |
|---|---|
| プロジェクトID | training-assistant-prod |
| プロジェクト名 | Training Assistant |

### 1-4. リージョン設定

    gcloud config set compute/region asia-northeast1
    gcloud config set compute/zone asia-northeast1-a

| 設定 | 値 | 意味 |
|---|---|---|
| region | asia-northeast1 | 東京リージョン |
| zone | asia-northeast1-a | 東京リージョン内のゾーンA |

### 1-5. 課金アカウントリンク

    # 課金アカウント一覧を確認
    gcloud billing accounts list

    # プロジェクトに課金アカウントをリンク
    gcloud billing projects link training-assistant-prod \
        --billing-account=YOUR_ACCOUNT_ID

※ 無料枠利用でもGCPは課金アカウントの紐付けが必須

### 1-6. API有効化

    gcloud services enable \
        bigquery.googleapis.com \
        cloudfunctions.googleapis.com \
        cloudscheduler.googleapis.com \
        secretmanager.googleapis.com \
        cloudbuild.googleapis.com \
        run.googleapis.com

| API | 用途 |
|---|---|
| bigquery.googleapis.com | データウェアハウス |
| cloudfunctions.googleapis.com | Cloud Functions |
| cloudscheduler.googleapis.com | Cloud Scheduler |
| secretmanager.googleapis.com | Secret Manager |
| cloudbuild.googleapis.com | Cloud Functions のデプロイに必要 |
| run.googleapis.com | Cloud Functions 2nd gen の基盤 |

### 1-7. サービスアカウント作成

#### dbt実行用

    gcloud iam service-accounts create sa-dbt-runner \
        --display-name="dbt Runner"

    gcloud projects add-iam-policy-binding training-assistant-prod \
        --member="serviceAccount:sa-dbt-runner@training-assistant-prod.iam.gserviceaccount.com" \
        --role="roles/bigquery.dataEditor"

    gcloud projects add-iam-policy-binding training-assistant-prod \
        --member="serviceAccount:sa-dbt-runner@training-assistant-prod.iam.gserviceaccount.com" \
        --role="roles/bigquery.jobUser"

#### Cloud Functions通知用

    gcloud iam service-accounts create sa-cf-notifier \
        --display-name="Cloud Functions Notifier"

    gcloud projects add-iam-policy-binding training-assistant-prod \
        --member="serviceAccount:sa-cf-notifier@training-assistant-prod.iam.gserviceaccount.com" \
        --role="roles/bigquery.dataViewer"

    gcloud projects add-iam-policy-binding training-assistant-prod \
        --member="serviceAccount:sa-cf-notifier@training-assistant-prod.iam.gserviceaccount.com" \
        --role="roles/bigquery.jobUser"

    gcloud projects add-iam-policy-binding training-assistant-prod \
        --member="serviceAccount:sa-cf-notifier@training-assistant-prod.iam.gserviceaccount.com" \
        --role="roles/secretmanager.secretAccessor"

#### Streamlit用

    gcloud iam service-accounts create sa-streamlit-app \
        --display-name="Streamlit Application"

    gcloud projects add-iam-policy-binding training-assistant-prod \
        --member="serviceAccount:sa-streamlit-app@training-assistant-prod.iam.gserviceaccount.com" \
        --role="roles/bigquery.dataEditor"

    gcloud projects add-iam-policy-binding training-assistant-prod \
        --member="serviceAccount:sa-streamlit-app@training-assistant-prod.iam.gserviceaccount.com" \
        --role="roles/bigquery.jobUser"

#### サービスアカウント権限まとめ

| アカウント | 用途 | BigQuery | Secret Manager |
|---|---|---|---|
| sa-dbt-runner | データ変換 | dataEditor + jobUser | なし |
| sa-cf-notifier | LINE通知 | dataViewer + jobUser | secretAccessor |
| sa-streamlit-app | 入力UI・可視化 | dataEditor + jobUser | なし |

### 1-8. サービスアカウントキー生成

    gcloud iam service-accounts keys create ./secrets/sa-streamlit-app.json \
        --iam-account=sa-streamlit-app@training-assistant-prod.iam.gserviceaccount.com

    gcloud iam service-accounts keys create ./secrets/sa-dbt-runner.json \
        --iam-account=sa-dbt-runner@training-assistant-prod.iam.gserviceaccount.com

| ファイル | 用途 | Git管理 |
|---|---|---|
| secrets/sa-streamlit-app.json | Streamlit → BigQuery接続用 | ❌ .gitignoreで除外 |
| secrets/sa-dbt-runner.json | dbt → BigQuery接続用 | ❌ .gitignoreで除外 |

確認:

    # .gitignoreで除外されていることを確認
    git status
    # → secrets/ 配下のファイルが表示されないこと

### 1-9. LINE Messaging API チャネル作成

手順:

1. LINE Developers (https://developers.line.biz/console/) でプロバイダー作成
   - プロバイダー名: MyFitnessProject

2. Messaging API チャネル作成
   - LINE Developers コンソールから「Messaging API」を選択
   - チャネル名: トレーニングアシスタント

3. LINE Official Account Manager に自動遷移
   - https://manager.line.biz/ の設定画面から「Messaging API」を有効化
   - プロバイダー「MyFitnessProject」を選択して紐付け

4. LINE Developers コンソールに戻りチャネル表示を確認

5. 認証情報を取得
   - チャネル基本設定タブ: チャネルシークレット
   - Messaging API設定タブ: チャネルアクセストークン（長期）を発行

| 項目 | 場所 | 用途 |
|---|---|---|
| チャネルシークレット | チャネル基本設定タブ | 署名の検証 |
| チャネルアクセストークン（長期） | Messaging API設定タブ最下部 | メッセージ送信 |

※ LINE Developers コンソールとLINE Official Account Managerは別サイト
※ Messaging APIの有効化はOfficial Account Manager側から行う

### 1-10. Secret Manager にAPIキー格納

    # チャネルアクセストークンを格納
    echo -n "YOUR_CHANNEL_ACCESS_TOKEN" | \
        gcloud secrets create line-channel-access-token \
        --data-file=- \
        --replication-policy="automatic"

    # チャネルシークレットを格納
    echo -n "YOUR_CHANNEL_SECRET" | \
        gcloud secrets create line-channel-secret \
        --data-file=- \
        --replication-policy="automatic"

    # 確認
    gcloud secrets list

    # 値の先頭20文字で正しく保存されたか確認
    gcloud secrets versions access latest --secret="line-channel-access-token" | cut -c 1-20

| シークレット名 | 内容 | 参照元 |
|---|---|---|
| line-channel-access-token | LINE チャネルアクセストークン | Cloud Functions (sa-cf-notifier) |
| line-channel-secret | LINE チャネルシークレット | Cloud Functions (sa-cf-notifier) |

### 1-11. 予算アラート設定

手順:

1. GCPコンソール > 課金 > 予算とアラート
2. 予算を作成
   - 名前: Training Assistant Budget
   - プロジェクト: training-assistant-prod
   - 予算額: $0
   - アラートのしきい値: デフォルト
   - 通知先: メール（デフォルト）

※ 無料枠超過の即座検知。$0設定で少しでも課金が発生したら通知。

### 1-12. 設定確認

    # プロジェクト設定
    gcloud config list

    # 有効なAPI一覧
    gcloud services list --enabled

    # サービスアカウント一覧
    gcloud iam service-accounts list

    # シークレット一覧
    gcloud secrets list

期待結果:

    プロジェクト: training-assistant-prod
    リージョン: asia-northeast1
    API: 6つ有効
    SA: 3つ作成済み
    シークレット: 2つ格納済み

---

## 完了チェックリスト

- [ ] gcloud CLI インストール済み・ログイン済み
- [ ] プロジェクト training-assistant-prod 作成済み
- [ ] リージョン asia-northeast1 設定済み
- [ ] 課金アカウントリンク済み
- [ ] API 6つ有効化済み
- [ ] サービスアカウント 3つ作成済み（sa-dbt-runner, sa-cf-notifier, sa-streamlit-app）
- [ ] サービスアカウントキー 2つ生成済み（secrets/配下）
- [ ] LINE Messaging API チャネル作成済み
- [ ] Secret Manager にLINE認証情報 2つ格納済み
- [ ] 予算アラート $0 設定済み
- [ ] secrets/ が .gitignore で除外されていることを確認済み

