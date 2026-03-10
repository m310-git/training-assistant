import streamlit as st
import uuid
from datetime import datetime
from utils.auth import check_password
from utils.bigquery_client import query, insert_rows

if not check_password():
    st.stop()

st.title("➕ 種目追加リクエスト")

user_id = st.session_state.user_id

# --- 新規リクエスト ---
st.subheader("新規リクエスト")

body_parts = query("SELECT body_part_id, body_part_name FROM mart.d_body_part ORDER BY sort_order")

exercise_name = st.text_input("種目名", max_chars=30)
selected_bp = st.selectbox(
    "部位",
    options=body_parts['body_part_id'].tolist(),
    format_func=lambda x: body_parts[body_parts['body_part_id']==x]['body_part_name'].values[0]
)
reason = st.text_area("追加理由（任意）", max_chars=500)

if st.button("📤 リクエスト送信"):
    if not exercise_name or len(exercise_name) < 2:
        st.error("種目名を2文字以上で入力してください")
    else:
        # 既存種目との重複チェック
        existing = query(f"""
            SELECT COUNT(*) AS cnt
            FROM raw.exercise_master
            WHERE LOWER(exercise_name) = LOWER('{exercise_name}')
        """)
        if existing['cnt'].iloc[0] > 0:
            st.error("既に登録されている種目です")
        else:
            # 承認待ちリクエストとの重複チェック
            pending = query(f"""
                SELECT COUNT(*) AS cnt
                FROM raw.exercise_request
                WHERE LOWER(exercise_name) = LOWER('{exercise_name}')
                  AND status = 'pending'
            """)
            if pending['cnt'].iloc[0] > 0:
                st.warning("同じ種目名のリクエストが既に承認待ちです")
            else:
                row = {
                    'request_id': str(uuid.uuid4()),
                    'user_id': user_id,
                    'exercise_name': exercise_name,
                    'body_part_id': selected_bp,
                    'reason': reason if reason else None,
                    'status': 'pending',
                    'reviewed_by': None,
                    'created_at': datetime.utcnow().isoformat(),
                    'reviewed_at': None
                }
                try:
                    insert_rows('training-assistant-prod.raw.exercise_request', [row])
                    st.success("リクエストを送信しました！管理者の承認をお待ちください。")
                except Exception as e:
                    st.error(f"送信エラー: {e}")

# --- リクエスト履歴 ---
st.markdown("---")
st.subheader("📋 リクエスト履歴")

history = query(f"""
    SELECT
        created_at,
        exercise_name,
        body_part_id,
        status,
        reviewed_at
    FROM raw.exercise_request
    WHERE user_id = '{user_id}'
    ORDER BY created_at DESC
""")

if not history.empty:
    status_icons = {"pending": "⏳ 承認待ち", "approved": "✅ 承認済み", "rejected": "❌ 却下"}
    for _, row in history.iterrows():
        icon = status_icons.get(row['status'], row['status'])
        st.markdown(
            f"**{row['created_at'].strftime('%Y/%m/%d')}** "
            f"{row['exercise_name']}（{row['body_part_id']}）　{icon}"
        )
else:
    st.info("リクエスト履歴はありません")