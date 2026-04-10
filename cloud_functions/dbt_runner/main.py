import functions_framework
import json
import subprocess
import uuid
from datetime import datetime
from google.cloud import bigquery, secretmanager
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, PushMessageRequest, TextMessage
)

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

def send_daily_notifications():
    """日次通知（3日未実施 + 7日空き部位別）"""
    if not should_send('3day'):
        print("Daily notification suppressed: monthly limit")
        return

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
            f"📱 アプリを開く: https://training-assistant-m310.streamlit.app/"
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
                f"📱 アプリを開く: https://training-assistant-m310.streamlit.app/"
            )
            try:
                send_line_message(row.line_user_id, message)
                log_notification(row.user_id, '7day', 'sent')
            except Exception as e:
                log_notification(row.user_id, '7day', 'failed')
                print(f"Error sending 7day notification to {row.user_id}: {e}")

def run_dbt(command, select=None):
    cmd = ["dbt", command, "--project-dir", "/workspace/dbt", "--profiles-dir", "/workspace/dbt"]
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
    """日次パイプライン: dbt run + test + 日次通知 + ML再学習（月曜のみ）"""
    try:
        # 1. dbt run
        run_dbt("run")

        # 2. dbt test
        run_dbt("test")

        # 3. 日次通知
        send_daily_notifications()

        # 4. ML再学習（月曜のみ）
        today = datetime.now().weekday()  # 0=月曜
        if today == 0:
            retrain_ml_model()
            run_dbt("run", select="m_ml_suggestion")

        return json.dumps({"status": "completed"})

    except Exception as e:
        print(f"Pipeline error: {e}")
        return json.dumps({"status": "error", "message": str(e)}), 500