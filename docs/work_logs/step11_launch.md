
# Step 11: 本番ローンチ

## 概要

Streamlit Cloudにデプロイし、本番環境での最終確認を行い、ユーザーに展開する。

## 前提条件

- [ ] Step 10 完了（E2Eテスト全シナリオPASS）
- [ ] GitHubリポジトリにmainブランチの最新コードがpush済み

---

## 手順

### 11-1. Streamlit Cloudアカウント作成

    1. https://share.streamlit.io/ にアクセス
    2. GitHubアカウントでサインアップ
    3. メール認証を完了

### 11-2. Streamlit Cloudアプリ作成

    1. 「New app」をクリック
    2. 以下を設定:

| 項目 | 設定値 |
|---|---|
| Repository | YOUR_USERNAME/training-assistant |
| Branch | main |
| Main file path | streamlit/app.py |
| App URL | training-assistant-XXXX.streamlit.app（自動生成） |

    3. 「Advanced settings」を開く
    4. Python version: 3.11 を選択
    5. 「Deploy!」をクリック

### 11-3. Streamlit Cloud Secrets設定

    1. デプロイされたアプリの設定画面を開く
    2. 「Secrets」タブを開く
    3. 以下の内容を貼り付け:

    [gcp_service_account]
    type = "service_account"
    project_id = "training-assistant-prod"
    private_key_id = "YOUR_KEY_ID"
    private_key = "-----BEGIN PRIVATE KEY-----\nYOUR_PRIVATE_KEY\n-----END PRIVATE KEY-----\n"
    client_email = "sa-streamlit-app@training-assistant-prod.iam.gserviceaccount.com"
    client_id = "YOUR_CLIENT_ID"
    auth_uri = "https://accounts.google.com/o/oauth2/auth"
    token_uri = "https://oauth2.googleapis.com/token"
    auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
    client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/sa-streamlit-app%40training-assistant-prod.iam.gserviceaccount.com"

    [passwords]
    user_001 = "hashed_password_1"
    user_002 = "hashed_password_2"
    user_003 = "hashed_password_3"

    [users]
    [users.user_001]
    name = "ユーザー1"
    is_admin = true
    [users.user_002]
    name = "ユーザー2"
    is_admin = false
    [users.user_003]
    name = "ユーザー3"
    is_admin = false

    4. 「Save」をクリック
    5. アプリが自動で再起動される

※ secrets/sa-streamlit-app.json の内容をTOML形式に変換して貼り付ける
※ private_key の改行は \n に変換すること

### 11-4. Streamlit Cloud動作確認

    アプリURL: https://training-assistant-XXXX.streamlit.app

確認項目:
- [ ] ログイン画面が表示される
- [ ] 各ユーザーでログインできる
- [ ] Input画面でBigQueryへの読み書きが動作する
- [ ] Dashboard画面でグラフが表示される
- [ ] Calendar画面が表示される
- [ ] Ranking画面が表示される
- [ ] Social画面が表示される
- [ ] ExerciseRequest画面が動作する
- [ ] Admin画面が管理者のみアクセス可能

### 11-5. Cloud FunctionsのURL更新

LINE通知メッセージ内のアプリURLを本番URLに更新:

#### cloud_functions/notifier/main.py

全ての "https://your-app.streamlit.app" を
"https://training-assistant-XXXX.streamlit.app" に置換

    # デプロイ
    gcloud functions deploy notifier-daily \
        --gen2 \
        --runtime=python311 \
        --region=asia-northeast1 \
        --source=cloud_functions/notifier \
        --entry-point=handle_daily_notification \
        --trigger-http \
        --service-account=sa-cf-notifier@training-assistant-prod.iam.gserviceaccount.com \
        --no-allow-unauthenticated

    gcloud functions deploy notifier-weekly-ranking \
        --gen2 \
        --runtime=python311 \
        --region=asia-northeast1 \
        --source=cloud_functions/notifier \
        --entry-point=handle_weekly_ranking \
        --trigger-http \
        --service-account=sa-cf-notifier@training-assistant-prod.iam.gserviceaccount.com \
        --no-allow-unauthenticated

    gcloud functions deploy notifier-monthly-ranking \
        --gen2 \
        --runtime=python311 \
        --region=asia-northeast1 \
        --source=cloud_functions/notifier \
        --entry-point=handle_monthly_ranking \
        --trigger-http \
        --service-account=sa-cf-notifier@training-assistant-prod.iam.gserviceaccount.com \
        --no-allow-unauthenticated

    gcloud functions deploy notifier-start \
        --gen2 \
        --runtime=python311 \
        --region=asia-northeast1 \
        --source=cloud_functions/notifier \
        --entry-point=handle_start_notification \
        --trigger-http \
        --service-account=sa-cf-notifier@training-assistant-prod.iam.gserviceaccount.com \
        --no-allow-unauthenticated

### 11-6. LINE公式アカウントの友だち追加

    1. LINE公式アカウントのQRコードを取得
       - LINE Official Account Manager > ホーム > 友だち追加 > QRコード

    2. 3名のユーザーにQRコードを共有し、友だち追加してもらう

    3. 各ユーザーのLINE user_id を取得
       - Webhook経由、またはLINE Developers コンソールで確認

    4. BigQueryのuser_masterを更新

        bq query --use_legacy_sql=false \
            "UPDATE raw.user_master SET line_user_id = '実際のLINE_USER_ID_1' WHERE user_id = 'user_001'"

        bq query --use_legacy_sql=false \
            "UPDATE raw.user_master SET line_user_id = '実際のLINE_USER_ID_2' WHERE user_id = 'user_002'"

        bq query --use_legacy_sql=false \
            "UPDATE raw.user_master SET line_user_id = '実際のLINE_USER_ID_3' WHERE user_id = 'user_003'"

    5. dbt run で mart.d_user を更新

        cd dbt
        dbt run --select d_user

### 11-7. LINE通知の本番テスト

    # 筋トレ開始通知テスト
    gcloud functions call notifier-start \
        --region=asia-northeast1 \
        --data='{"user_id": "user_001", "body_part": "胸"}'

    # 日次通知テスト
    gcloud functions call notifier-daily \
        --region=asia-northeast1 \
        --data='{}'

    # 週間ランキング通知テスト
    gcloud functions call notifier-weekly-ranking \
        --region=asia-northeast1 \
        --data='{}'

確認項目:
- [ ] 各ユーザーのLINEに通知が届く
- [ ] 通知内のアプリURLが本番URLになっている
- [ ] notification_log にログが記録される

### 11-8. Cloud Scheduler最終確認

    gcloud scheduler jobs list --location=asia-northeast1

| ジョブ名 | スケジュール | 状態 |
|---|---|---|
| daily-pipeline | 0 6 * * * | ENABLED |
| weekly-ranking | 0 8 * * 1 | ENABLED |
| monthly-ranking | 0 8 1 * * | ENABLED |

翌朝06:00 JSTにdaily-pipelineが自動実行されることを確認:

    # 翌日のログを確認
    gcloud functions logs read dbt-runner \
        --region=asia-northeast1 \
        --limit=20

### 11-9. テストデータのクリーンアップ

本番運用前にテストデータを論理削除:

    bq query --use_legacy_sql=false \
        "UPDATE raw.training_log SET is_deleted = TRUE, updated_at = CURRENT_TIMESTAMP() WHERE log_id LIKE 'test-%'"

    # dbt run で mart を更新
    cd dbt
    dbt run

### 11-10. パスワードの本番化

    1. 各ユーザーの本番パスワードを決定
    2. ハッシュ化

        python -c "import hashlib; print(hashlib.sha256('本番パスワード'.encode()).hexdigest())"

    3. Streamlit Cloud の Secrets を更新
       - [passwords] セクションのハッシュ値を本番用に差し替え

    4. ローカルの secrets.toml も更新

### 11-11. 最終Gitコミット＆プッシュ

    git add cloud_functions/ docs/work_logs/
    git commit -m "feat: production launch - URL update and final configuration"
    git push origin main

### 11-12. ユーザーへの展開

    1. 3名のユーザーに以下を共有:
       - アプリURL: https://training-assistant-XXXX.streamlit.app
       - ユーザーID
       - パスワード
       - LINE公式アカウントのQRコード（未追加の場合）

    2. 使い方の簡単な説明:
       - ログイン方法
       - トレーニング記録の入力方法
       - ダッシュボード・ランキングの見方
       - LINE通知について

---

## 本番環境の構成

    Streamlit Cloud
    └── https://training-assistant-XXXX.streamlit.app
        ├── 📝 Input（トレーニング入力）
        ├── 📅 Calendar（カレンダー）
        ├── 📊 Dashboard（ダッシュボード）
        ├── 🏆 Ranking（ランキング）
        ├── 👥 Social（ソーシャル）
        ├── ➕ ExerciseRequest（種目リクエスト）
        └── ⚙️ Admin（管理者画面）

    GCP (training-assistant-prod)
    ├── BigQuery
    │   ├── raw（5テーブル）
    │   ├── staging（1テーブル）
    │   └── mart（13テーブル + 1 MLモデル）
    ├── Cloud Functions
    │   ├── dbt-runner（日次パイプライン）
    │   ├── notifier-daily（日次通知）
    │   ├── notifier-weekly-ranking（週間ランキング通知）
    │   ├── notifier-monthly-ranking（月間ランキング通知）
    │   └── notifier-start（筋トレ開始通知）
    ├── Cloud Scheduler
    │   ├── daily-pipeline（毎日 06:00 JST）
    │   ├── weekly-ranking（毎週月曜 08:00 JST）
    │   └── monthly-ranking（毎月1日 08:00 JST）
    ├── Secret Manager
    │   ├── line-channel-access-token
    │   └── line-channel-secret
    └── IAM
        ├── sa-dbt-runner
        ├── sa-cf-notifier
        └── sa-streamlit-app

    LINE Messaging API
    └── トレーニングアシスタント（公式アカウント）

---

## 運用開始後の日常

    毎日自動:
    06:00 - dbt run + dbt test（日次パイプライン）
    06:00 - 月曜のみ: BigQuery MLモデル再学習
    07:00 - 日次通知判定・送信（3日未実施・7日空き）

    毎週自動:
    月曜 08:00 - 週間ランキング通知

    毎月自動:
    1日 08:00 - 月間ランキング通知

    ユーザー操作時:
    トレーニング記録入力 → 自動保存 → 初回のみ筋トレ開始通知

---

## 完了チェックリスト

- [ ] Streamlit Cloudアカウント作成済み
- [ ] アプリがデプロイされている
- [ ] Secrets が設定されている
- [ ] 本番URLでログイン・全画面が動作する
- [ ] Cloud FunctionsのURLが本番URLに更新されている
- [ ] LINE公式アカウントに3名が友だち追加済み
- [ ] LINE user_id がBigQueryに登録されている
- [ ] LINE通知が全ユーザーに届く
- [ ] Cloud Schedulerが有効（3ジョブ）
- [ ] テストデータがクリーンアップ済み
- [ ] パスワードが本番用に更新されている
- [ ] ユーザーにURL・パスワードを共有済み
- [ ] Gitにpush済み

---

## 🎉 ローンチ完了！

Phase 1 (MVP) の構築が完了しました。

次のステップ:
- Phase 2: データ品質（dbt-expectations + Elementary）
- Phase 3: 自動化（Prefect Cloud）
- Phase 4: IaC（Terraform）

