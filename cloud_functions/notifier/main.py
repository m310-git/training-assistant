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