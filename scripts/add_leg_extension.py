"""
種目マスタにレッグエクステンションを追加するスクリプト
"""

from google.cloud import bigquery
from google.oauth2 import service_account
import toml
import os

# .streamlit/secrets.toml からサービスアカウント情報を読み込み
secrets_path = os.path.join(os.path.dirname(__file__), "..", "streamlit", ".streamlit", "secrets.toml")
with open(secrets_path, "r", encoding="utf-8") as f:
    secrets = toml.load(f)

# サービスアカウント情報を取得
service_account_info = secrets["gcp_service_account"]

# サービスアカウントクレデンシャルを作成
credentials = service_account.Credentials.from_service_account_info(service_account_info)

# BigQuery クライアントの初期化
client = bigquery.Client(
    credentials=credentials,
    project="training-assistant-prod"
)

# INSERT 文の実行
query = """
INSERT INTO `training-assistant-prod.raw.exercise_master` VALUES
    ('leg_extension', 'レッグエクステンション', 'leg', FALSE, TRUE, 4, CURRENT_TIMESTAMP());
"""

try:
    job = client.query(query)
    job.result()  # クエリの完了を待つ
    print("レッグエクステンションを種目マスタに追加しました")
except Exception as e:
    print(f"エラーが発生しました: {e}")
