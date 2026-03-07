
# Step 7: Cloud Functions + Cloud Scheduler

## 概要

LINE通知を送信するCloud Functionsと、日次・週次・月次バッチを起動するCloud Schedulerを構築する。

## 前提条件

- [ ] Step 4 完了（dbtモデルが動作している）
- [ ] Secret Manager にLINE認証情報が格納済み
- [ ] sa-cf-notifier サービスアカウントが作成済み

---

## 手順

### 7-1. 通知用Cloud Function作成

#### cloud_functions/notifier/main.py

    import functions_framework
    import json
    import uuid
    from datetime import datetime
    from google.cloud import bigquery, secretmanager
    from linebot.v3.messaging import (
        Configuration, ApiClient, MessagingApi, PushMessageRequest, TextMessage
    )

    # BigQueryクライアント
    bq_client = bigquery.Client()

    def get_secret(secret_id):
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/training-assistant-prod/secrets/{secret_id}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")

    def get_line_api():
        token = get_secret("line-channel-access-token")
        configuration = Configuration(access_token=token)
        api_client = ApiClient(configuration)
        return MessagingApi(api_client)

    def send_line_message(line_user_id, message):
        api = get_line_api()
        api.push_message(
            PushMessageRequest(
                to=line_user_id,
                messages=[TextMessage(text=message)]
            )
        )

    def log_notification(user_id, notification_type, status):
        table_id = "training-assistant-prod.raw.notification_log"
        row = {
            "notification_id": str(uuid.uuid4()),
            "user_id": user_id,
            "notification_type": notification_type,
            "status": status,
            "sent_at": datetime.utcnow().isoformat()
        }
        bq_client.insert_rows_json(table_id, [row])

    def get_monthly_notification_count():
        query = """
            SELECT COUNT(*) AS cnt
            FROM raw.notification_log
            WHERE status = 'sent'
              AND sent_at >= TIMESTAMP_TRUNC(CURRENT_TIMESTAMP(), MONTH, 'Asia/Tokyo')
        """
        result = bq_client.query(query).result()
        for row in result:
            return row.cnt
        return 0

    def should_send(notification_type):
        count = get_monthly_notification_count()
        if count >= 200:
            return False
        if count >= 190 and notification_type in ['3day', '7day']:
            return False
        if count >= 180 and notification_type == '7day':
            return False
        return True

    @functions_framework.http
    def handle_daily_notification(request):
        """日次通知（3日未実施 + 7日空き部位別）"""
        if not should_send('3day'):
            return json.dumps({"status": "suppressed", "reason": "monthly limit"})

        # 3日未実施リマインド
        query_3day = """
            SELECT DISTINCT
                m.user_id,
                u.line_user_id,
                u.user_name,
                m.days_since_last_any
            FROM mart.m_last_training m
            JOIN mart.d_user u ON m.user_id = u.user_id
            WHERE m.needs_3day_reminder = TRUE
        """
        results_3day = bq_client.query(query_3day).result()

        for row in results_3day:
            if not should_send('3day'):
                log_notification(row.user_id, '3day', 'suppressed')
                continue

            message = (
                f"⚠️ {row.days_since_last_any}日間トレーニングしていません！\n\n"
                f"💪 今日もトレーニングしましょう！\n"
                f"📱 アプリを開く: https://your-app.streamlit.app"
            )
            try:
                send_line_message(row.line_user_id, message)
                log_notification(row.user_id, '3day', 'sent')
            except Exception as e:
                log_notification(row.user_id, '3day', 'failed')
                print(f"Error sending 3day notification to {row.user_id}: {e}")

        # 7日空き（部位別）
        if should_send('7day'):
            query_7day = """
                SELECT
                    m.user_id,
                    u.line_user_id,
                    m.body_part_name,
                    m.last_training_date
                FROM mart.m_last_training m
                JOIN mart.d_user u ON m.user_id = u.user_id
                WHERE m.needs_7day_reminder = TRUE
            """
            results_7day = bq_client.query(query_7day).result()

            for row in results_7day:
                if not should_send('7day'):
                    log_notification(row.user_id, '7day', 'suppressed')
                    continue

                message = (
                    f"⚠️ 「{row.body_part_name}」のトレーニングが7日以上空いています！\n"
                    f"最後の{row.body_part_name}トレ: {row.last_training_date}\n\n"
                    f"📱 アプリを開く: https://your-app.streamlit.app"
                )
                try:
                    send_line_message(row.line_user_id, message)
                    log_notification(row.user_id, '7day', 'sent')
                except Exception as e:
                    log_notification(row.user_id, '7day', 'failed')
                    print(f"Error sending 7day notification to {row.user_id}: {e}")

        return json.dumps({"status": "completed"})

    @functions_framework.http
    def handle_weekly_ranking(request):
        """週間ランキング通知"""
        query = """
            SELECT
                r.user_id,
                u.line_user_id,
                r.user_name,
                r.total_volume,
                r.rank,
                r.rank_change,
                r.prev_rank,
                r.week_start,
                r.week_end
            FROM mart.m_ranking_weekly r
            JOIN mart.d_user u ON r.user_id = u.user_id
            WHERE r.week_start = (
                SELECT MAX(week_start) FROM mart.m_ranking_weekly
            )
            ORDER BY r.rank
        """
        results = list(bq_client.query(query).result())

        if not results:
            return json.dumps({"status": "no_data"})

        week_start = results[0].week_start
        week_end = results[0].week_end

        # ランキングメッセージ構築
        rank_icons = {1: "🥇", 2: "🥈", 3: "🥉"}
        change_icons = {"UP": "↑", "DOWN": "↓", "SAME": "→", "NEW": "NEW"}

        lines = [f"🏆 週間ランキング（{week_start}〜{week_end}）\n"]
        for r in results:
            icon = rank_icons.get(r.rank, f"{r.rank}位")
            change = change_icons.get(r.rank_change, "")
            prev = f"(前回{r.prev_rank}位)" if r.prev_rank else ""
            lines.append(
                f"{icon} {r.user_name}: {r.total_volume:,.0f} kg  {change} {prev}"
            )
        lines.append(f"\n📱 詳細を見る: https://your-app.streamlit.app")

        message = "\n".join(lines)

        # 全ユーザーに送信
        users = bq_client.query("SELECT user_id, line_user_id FROM mart.d_user").result()
        for user in users:
            if not should_send('weekly_ranking'):
                log_notification(user.user_id, 'weekly_ranking', 'suppressed')
                continue
            try:
                send_line_message(user.line_user_id, message)
                log_notification(user.user_id, 'weekly_ranking', 'sent')
            except Exception as e:
                log_notification(user.user_id, 'weekly_ranking', 'failed')
                print(f"Error sending weekly ranking to {user.user_id}: {e}")

        return json.dumps({"status": "completed"})

    @functions_framework.http
    def handle_monthly_ranking(request):
        """月間ランキング通知"""
        query = """
            SELECT
                r.user_id,
                u.line_user_id,
                r.user_name,
                r.total_volume,
                r.rank,
                r.rank_change,
                r.prev_rank,
                r.month
            FROM mart.m_ranking_monthly r
            JOIN mart.d_user u ON r.user_id = u.user_id
            WHERE r.month = (
                SELECT MAX(month) FROM mart.m_ranking_monthly
            )
            ORDER BY r.rank
        """
        results = list(bq_client.query(query).result())

        if not results:
            return json.dumps({"status": "no_data"})

        month = results[0].month

        rank_icons = {1: "🥇", 2: "🥈", 3: "🥉"}
        change_icons = {"UP": "↑", "DOWN": "↓", "SAME": "→", "NEW": "NEW"}

        lines = [f"🏆 月間ランキング（{month.strftime('%Y年%m月')}）\n"]
        for r in results:
            icon = rank_icons.get(r.rank, f"{r.rank}位")
            change = change_icons.get(r.rank_change, "")
            prev = f"(前回{r.prev_rank}位)" if r.prev_rank else ""
            lines.append(
                f"{icon} {r.user_name}: {r.total_volume:,.0f} kg  {change} {prev}"
            )
        lines.append(f"\n📱 詳細を見る: https://your-app.streamlit.app")

        message = "\n".join(lines)

        users = bq_client.query("SELECT user_id, line_user_id FROM mart.d_user").result()
        for user in users:
            if not should_send('monthly_ranking'):
                log_notification(user.user_id, 'monthly_ranking', 'suppressed')
                continue
            try:
                send_line_message(user.line_user_id, message)
                log_notification(user.user_id, 'monthly_ranking', 'sent')
            except Exception as e:
                log_notification(user.user_id, 'monthly_ranking', 'failed')
                print(f"Error sending monthly ranking to {user.user_id}: {e}")

        return json.dumps({"status": "completed"})

    @functions_framework.http
    def handle_start_notification(request):
        """筋トレ開始通知（Streamlitから呼び出し）"""
        data = request.get_json()
        user_id = data.get('user_id')
        body_part = data.get('body_part')

        if not user_id or not body_part:
            return json.dumps({"status": "error", "message": "missing params"}), 400

        # 本日既に開始通知を送信済みか確認
        check = bq_client.query(f"""
            SELECT COUNT(*) AS cnt
            FROM raw.notification_log
            WHERE user_id = '{user_id}'
              AND notification_type = 'start'
              AND status = 'sent'
              AND sent_at >= TIMESTAMP_TRUNC(CURRENT_TIMESTAMP(), DAY, 'Asia/Tokyo')
        """).result()

        for row in check:
            if row.cnt > 0:
                return json.dumps({"status": "already_sent"})

        if not should_send('start'):
            log_notification(user_id, 'start', 'suppressed')
            return json.dumps({"status": "suppressed"})

        # ユーザー情報取得
        user = list(bq_client.query(f"""
            SELECT user_name, line_user_id FROM mart.d_user WHERE user_id = '{user_id}'
        """).result())[0]

        # 他の全ユーザーに通知
        other_users = bq_client.query(f"""
            SELECT user_id, line_user_id FROM mart.d_user WHERE user_id != '{user_id}'
        """).result()

        message = (
            f"🏋️ {user.user_name}がトレーニングを開始しました！\n"
            f"今日のメニュー: {body_part}\n\n"
            f"📱 アプリを開く: https://your-app.streamlit.app"
        )

        for other in other_users:
            try:
                send_line_message(other.line_user_id, message)
                log_notification(other.user_id, 'start', 'sent')
            except Exception as e:
                log_notification(other.user_id, 'start', 'failed')
                print(f"Error sending start notification to {other.user_id}: {e}")

        return json.dumps({"status": "completed"})

#### cloud_functions/notifier/requirements.txt

    functions-framework==3.*
    google-cloud-bigquery>=3.0,<4.0
    google-cloud-secret-manager>=2.0,<3.0
    line-bot-sdk>=3.0,<4.0

### 7-2. dbt実行用Cloud Function作成

#### cloud_functions/dbt_runner/main.py

    import functions_framework
    import json
    import subprocess
    from datetime import datetime
    from google.cloud import bigquery

    bq_client = bigquery.Client()

    def run_dbt(command, select=None):
        cmd = ["dbt", command, "--project-dir", "/workspace/dbt"]
        if select:
            cmd.extend(["--select", select])
        result = subprocess.run(cmd, capture_output=True, text=True)
        print(f"dbt {command} stdout: {result.stdout}")
        print(f"dbt {command} stderr: {result.stderr}")
        if result.returncode != 0:
            raise Exception(f"dbt {command} failed: {result.stderr}")
        return result.stdout

    def retrain_ml_model():
        query = """
            CREATE OR REPLACE MODEL mart.training_predictor
            OPTIONS(
                model_type = 'BOOSTED_TREE_REGRESSOR',
                input_label_cols = ['next_weight_kg'],
                num_trials = 5,
                max_iterations = 50,
                early_stop = TRUE,
                data_split_method = 'AUTO_SPLIT'
            ) AS
            WITH training_pairs AS (
                SELECT
                    user_id, exercise_id, set_number, training_date,
                    weight_kg, reps, volume, rpe,
                    LAG(weight_kg) OVER w AS prev_weight_kg,
                    LAG(reps) OVER w AS prev_reps,
                    LAG(rpe) OVER w AS prev_rpe,
                    LAG(volume) OVER w AS prev_volume,
                    DATE_DIFF(training_date, LAG(training_date) OVER w, DAY) AS days_since_last,
                    weight_kg AS next_weight_kg
                FROM mart.fct_training_set
                WINDOW w AS (
                    PARTITION BY user_id, exercise_id, set_number
                    ORDER BY training_date
                )
            )
            SELECT
                prev_weight_kg, prev_reps, prev_rpe, prev_volume,
                set_number, days_since_last, next_weight_kg
            FROM training_pairs
            WHERE prev_weight_kg IS NOT NULL
              AND days_since_last IS NOT NULL
        """
        bq_client.query(query).result()
        print("ML model retrained successfully")

    @functions_framework.http
    def handle_daily_pipeline(request):
        """日次パイプライン: dbt run + test + ML再学習（月曜のみ）"""
        try:
            # 1. dbt run
            run_dbt("run")

            # 2. dbt test
            run_dbt("test")

            # 3. ML再学習（月曜のみ）
            today = datetime.now().weekday()  # 0=月曜
            if today == 0:
                retrain_ml_model()
                run_dbt("run", select="m_ml_suggestion")

            return json.dumps({"status": "completed"})

        except Exception as e:
            print(f"Pipeline error: {e}")
            return json.dumps({"status": "error", "message": str(e)}), 500

#### cloud_functions/dbt_runner/requirements.txt

    functions-framework==3.*
    google-cloud-bigquery>=3.0,<4.0
    dbt-bigquery>=1.7,<2.0

### 7-3. Cloud Functionsデプロイ

    # notifier（通知用）
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

    # dbt-runner（パイプライン用）
    gcloud functions deploy dbt-runner \
        --gen2 \
        --runtime=python311 \
        --region=asia-northeast1 \
        --source=cloud_functions/dbt_runner \
        --entry-point=handle_daily_pipeline \
        --trigger-http \
        --service-account=sa-dbt-runner@training-assistant-prod.iam.gserviceaccount.com \
        --no-allow-unauthenticated \
        --timeout=540

### 7-4. Cloud Scheduler設定

    # 日次パイプライン（毎日06:00 JST）
    gcloud scheduler jobs create http daily-pipeline \
        --location=asia-northeast1 \
        --schedule="0 6 * * *" \
        --time-zone="Asia/Tokyo" \
        --uri="https://asia-northeast1-training-assistant-prod.cloudfunctions.net/dbt-runner" \
        --http-method=POST \
        --oidc-service-account-email=sa-dbt-runner@training-assistant-prod.iam.gserviceaccount.com

    # 日次通知（毎日07:00 JST）→ daily-pipelineに統合
    # ※ dbt-runner完了後にnotifierを呼び出す形に変更する場合はここを修正

    # 週間ランキング通知（毎週月曜 08:00 JST）
    gcloud scheduler jobs create http weekly-ranking \
        --location=asia-northeast1 \
        --schedule="0 8 * * 1" \
        --time-zone="Asia/Tokyo" \
        --uri="https://asia-northeast1-training-assistant-prod.cloudfunctions.net/notifier-weekly-ranking" \
        --http-method=POST \
        --oidc-service-account-email=sa-cf-notifier@training-assistant-prod.iam.gserviceaccount.com

    # 月間ランキング通知（毎月1日 08:00 JST）
    gcloud scheduler jobs create http monthly-ranking \
        --location=asia-northeast1 \
        --schedule="0 8 1 * *" \
        --time-zone="Asia/Tokyo" \
        --uri="https://asia-northeast1-training-assistant-prod.cloudfunctions.net/notifier-monthly-ranking" \
        --http-method=POST \
        --oidc-service-account-email=sa-cf-notifier@training-assistant-prod.iam.gserviceaccount.com

    # 確認
    gcloud scheduler jobs list --location=asia-northeast1

期待結果:

    ID                LOCATION           SCHEDULE      STATE
    daily-pipeline    asia-northeast1    0 6 * * *     ENABLED
    weekly-ranking    asia-northeast1    0 8 * * 1     ENABLED
    monthly-ranking   asia-northeast1    0 8 1 * *     ENABLED

Cloud Scheduler 無料枠: 3ジョブ → ちょうど3ジョブで収まる

### 7-5. 動作確認

#### Cloud Functions の手動テスト

    # dbt-runner のテスト
    gcloud functions call dbt-runner \
        --region=asia-northeast1 \
        --data='{}'

    # 日次通知のテスト
    gcloud functions call notifier-daily \
        --region=asia-northeast1 \
        --data='{}'

    # 週間ランキング通知のテスト
    gcloud functions call notifier-weekly-ranking \
        --region=asia-northeast1 \
        --data='{}'

    # 筋トレ開始通知のテスト
    gcloud functions call notifier-start \
        --region=asia-northeast1 \
        --data='{"user_id": "user_001", "body_part": "胸"}'

#### ログ確認

    # notifier のログ
    gcloud functions logs read notifier-daily \
        --region=asia-northeast1 \
        --limit=20

    # dbt-runner のログ
    gcloud functions logs read dbt-runner \
        --region=asia-northeast1 \
        --limit=20

#### Cloud Scheduler の手動実行

    gcloud scheduler jobs run daily-pipeline \
        --location=asia-northeast1

    gcloud scheduler jobs run weekly-ranking \
        --location=asia-northeast1

確認項目:
- Cloud Functions がエラーなく実行される
- LINE通知が届く（仮LINE IDの場合はエラーログで確認）
- notification_log にレコードが記録される
- Cloud Scheduler からの起動が成功する

### 7-6. 通知カウンター確認

    bq query --use_legacy_sql=false \
        "SELECT notification_type, status, COUNT(*) AS cnt
         FROM raw.notification_log
         GROUP BY 1, 2
         ORDER BY 1, 2"

### 7-7. Gitコミット＆プッシュ

    git add cloud_functions/ docs/work_logs/
    git commit -m "feat: Cloud Functions (notifier + dbt-runner) and Cloud Scheduler"
    git push origin main

---

## 現在の構成

    cloud_functions/
    ├── dbt_runner/
    │   ├── main.py
    │   └── requirements.txt
    └── notifier/
        ├── main.py
        └── requirements.txt

    Cloud Scheduler:
    ├── daily-pipeline      (毎日 06:00 JST)
    ├── weekly-ranking      (毎週月曜 08:00 JST)
    └── monthly-ranking     (毎月1日 08:00 JST)

---

## 完了チェックリスト

- [ ] notifier Cloud Function がデプロイされている（4エントリポイント）
- [ ] dbt-runner Cloud Function がデプロイされている
- [ ] Cloud Scheduler 3ジョブが作成されている
- [ ] 日次通知（3日未実施・7日空き）が動作する
- [ ] 週間ランキング通知が動作する
- [ ] 月間ランキング通知が動作する
- [ ] 筋トレ開始通知が動作する
- [ ] 通知カウンター（notification_log）にログが記録される
- [ ] 通知抑制ロジック（180/190/200通）が実装されている
- [ ] Cloud Scheduler からの起動が成功する
- [ ] Gitにpush済み


