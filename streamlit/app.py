import streamlit as st
from datetime import date, timedelta
import calendar
from utils.auth import check_password
from utils.bigquery_client import query

st.set_page_config(
    page_title="トレーニングアシスタント",
    page_icon="🏋️",
    layout="wide"
)

if not check_password():
    st.stop()

user_id = st.session_state.user_id
user_name = st.session_state.user_name

st.title(f"🏋️ {user_name}さんのトレーニング")

# ============================================
# 1. 今週のカレンダー
# ============================================
st.subheader("📅 今週のトレーニング")

today = date.today()
# 今週の月曜日を取得
monday = today - timedelta(days=today.weekday())
sunday = monday + timedelta(days=6)

# 今週のデータ取得
week_data = query(f"""
    WITH deduped AS (
        SELECT
            *,
            ROW_NUMBER() OVER (
                PARTITION BY log_id
                ORDER BY updated_at DESC
            ) AS rn
        FROM raw.training_log
        WHERE user_id = '{user_id}'
          AND training_date BETWEEN '{monday}' AND '{sunday}'
    )
    SELECT
        training_date,
        STRING_AGG(DISTINCT body_part, ', ') AS body_parts,
        SUM(ROUND(weight_kg * reps, 1)) AS total_volume,
        COUNT(DISTINCT exercise_name) AS exercise_count
    FROM deduped
    WHERE rn = 1 AND is_deleted = FALSE
    GROUP BY training_date
    ORDER BY training_date
""")

week_dict = {}
if not week_data.empty:
    for _, row in week_data.iterrows():
        week_dict[row['training_date']] = row

# 曜日表示
day_names = ['月', '火', '水', '木', '金', '土', '日']
cols = st.columns(7)

for i in range(7):
    d = monday + timedelta(days=i)
    with cols[i]:
        # 今日はハイライト
        if d == today:
            st.markdown(f"**📍{day_names[i]}**")
        else:
            st.markdown(f"**{day_names[i]}**")

        st.markdown(f"{d.day}日")

        if d in week_dict:
            bp = week_dict[d]['body_parts']
            vol = week_dict[d]['total_volume']
            st.markdown(f"🟢{bp}")
            st.caption(f"{vol:,.0f}kg")
        else:
            if d <= today:
                st.markdown("ー")
            else:
                st.markdown("")

# 今週のサマリー
if week_dict:
    total_days = len(week_dict)
    total_vol = sum(row['total_volume'] for row in week_dict.values())
    st.markdown(f"**今週: {total_days}日 / 総負荷量: {total_vol:,.0f} kg**")

# ============================================
# 2. トレーニング入力ボタン
# ============================================
st.markdown("---")

if st.button("📝 トレーニングを記録する", use_container_width=True, type="primary"):
    st.switch_page("pages/1_📝_Input.py")

# ============================================
# 3. 週間総合ランキング
# ============================================
st.markdown("---")
st.subheader("🏆 週間ランキング")

try:
    weekly = query("""
        SELECT user_name, total_volume, rank, rank_change, prev_rank, week_start, week_end
        FROM mart.m_ranking_weekly
        WHERE week_start = (SELECT MAX(week_start) FROM mart.m_ranking_weekly)
        ORDER BY rank
    """)
except Exception:
    weekly = None

rank_icons = {1: "🥇", 2: "🥈", 3: "🥉"}
change_icons = {"UP": "↑", "DOWN": "↓", "SAME": "→", "NEW": "🆕"}

if weekly is not None and not weekly.empty:
    ws = weekly['week_start'].iloc[0]
    we = weekly['week_end'].iloc[0]
    st.caption(f"{ws} 〜 {we}")

    for _, row in weekly.iterrows():
        icon = rank_icons.get(row['rank'], f"{row['rank']}位")
        change = change_icons.get(row['rank_change'], "")
        vol = f"{row['total_volume']:,.0f} kg"

        # 自分の行をハイライト
        if row['user_name'] == user_name:
            st.markdown(f"**{icon} {row['user_name']}: {vol} {change}** ⬅️")
        else:
            st.markdown(f"{icon} {row['user_name']}: {vol} {change}")
else:
    st.info("ランキングデータがまだありません。トレーニングを記録しましょう！")

# ============================================
# 4. クイックリンク
# ============================================
st.markdown("---")

col1, col2, col3, col4 = st.columns(4)
with col1:
    if st.button("📅 カレンダー", use_container_width=True):
        st.switch_page("pages/2_📅_Calendar.py")
with col2:
    if st.button("📊 ダッシュボード", use_container_width=True):
        st.switch_page("pages/3_📊_Dashboard.py")
with col3:
    if st.button("🏆 ランキング", use_container_width=True):
        st.switch_page("pages/4_🏆_Ranking.py")
with col4:
    if st.button("👥 ソーシャル", use_container_width=True):
        st.switch_page("pages/5_👥_Social.py")

# ============================================
# フッター
# ============================================
st.markdown("---")
if st.button("🚪 ログアウト", use_container_width=True):
    st.session_state.clear()
    st.rerun()