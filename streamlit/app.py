import streamlit as st
from datetime import date, timedelta
from utils.auth import check_password, is_logged_in
from utils.bigquery_client import query

st.set_page_config(
    page_title="トレーニングアシスタント",
    page_icon="🏋️",
    layout="wide"
)

if is_logged_in():
    user_id = st.session_state.user_id
    user_name = st.session_state.user_name
    st.title(f"🏋️ {user_name}さん、こんにちは！")
else:
    st.title("🏋️ 閲覧者さん、こんにちは！")
    st.info("💡 ログインするとデータ入力ができます")
    users = query("SELECT user_id, user_name FROM mart.d_user ORDER BY user_id")
    user_id = st.selectbox(
        "表示するユーザー",
        options=users['user_id'].tolist(),
        format_func=lambda x: users[users['user_id']==x]['user_name'].values[0]
    )
    user_name = users[users['user_id']==user_id]['user_name'].values[0]

st.subheader(f"🏋️ {user_name}さんのトレーニング")

# ============================================
# 1. 今週のトレーニング
# ============================================
st.subheader("📅 今週のトレーニング")

today = date.today()
monday = today - timedelta(days=today.weekday())
sunday = monday + timedelta(days=6)

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
        d.training_date,
        STRING_AGG(DISTINCT bp.body_part_name, ', ') AS body_parts,
        SUM(ROUND(d.weight_kg * d.reps, 1)) AS total_volume,
        COUNT(DISTINCT d.exercise_name) AS exercise_count
    FROM deduped d
    LEFT JOIN mart.d_body_part bp ON d.body_part = bp.body_part_id
    WHERE d.rn = 1 AND d.is_deleted = FALSE
    GROUP BY d.training_date
    ORDER BY d.training_date
""")

week_dict = {}
if not week_data.empty:
    for _, row in week_data.iterrows():
        week_dict[row['training_date']] = row

day_names = ['月', '火', '水', '木', '金', '土', '日']

# HTML テーブルで横並び表示
html = """
<style>
.week-table { width: 100%; border-collapse: collapse; text-align: center; font-size: 13px; }
.week-table th { padding: 4px 2px; font-weight: bold; color: #555; }
.week-table td { padding: 4px 2px; }
.week-today { background-color: #FF6B6B; color: white; border-radius: 50%; padding: 1px 5px; font-weight: bold; }
.week-trained { color: #28a745; font-size: 11px; }
.week-rest { color: #ccc; }
</style>
<table class="week-table">
<tr>
"""

for name in day_names:
    html += f"<th>{name}</th>"
html += "</tr><tr>"

for i in range(7):
    d = monday + timedelta(days=i)
    day_num = d.day

    if d == today:
        day_html = f'<span class="week-today">{day_num}</span>'
    else:
        day_html = str(day_num)

    if d in week_dict:
        bp = week_dict[d]['body_parts']
        vol = week_dict[d]['total_volume']
        html += f'<td>{day_html}<br><span class="week-trained">🟢{bp}<br>{vol:,.0f}kg</span></td>'
    else:
        html += f'<td>{day_html}<br><span class="week-rest">ー</span></td>'

html += "</tr></table>"

st.markdown(html, unsafe_allow_html=True)

# 今週のサマリー
if week_dict:
    total_days = len(week_dict)
    total_vol = sum(row['total_volume'] for row in week_dict.values())
    st.success(f"📊 今週: {total_days}日 / 総負荷量: {total_vol:,.0f} kg")
else:
    st.info("今週はまだトレーニングしていません 💪")

# 先週のサマリー
last_monday = monday - timedelta(days=7)
last_sunday = monday - timedelta(days=1)

last_week_data = query(f"""
    WITH deduped AS (
        SELECT
            *,
            ROW_NUMBER() OVER (
                PARTITION BY log_id
                ORDER BY updated_at DESC
            ) AS rn
        FROM raw.training_log
        WHERE user_id = '{user_id}'
          AND training_date BETWEEN '{last_monday}' AND '{last_sunday}'
    )
    SELECT
        COUNT(DISTINCT training_date) AS training_days,
        SUM(ROUND(weight_kg * reps, 1)) AS total_volume
    FROM deduped
    WHERE rn = 1 AND is_deleted = FALSE
""")

if not last_week_data.empty and last_week_data['total_volume'].iloc[0]:
    lw_days = int(last_week_data['training_days'].iloc[0])
    lw_vol = last_week_data['total_volume'].iloc[0]

    # 今週との比較
    if week_dict:
        diff = total_vol - lw_vol
        diff_pct = (diff / lw_vol * 100) if lw_vol > 0 else 0
        st.caption(f"先週: {lw_days}日 / {lw_vol:,.0f} kg（差分: {diff:+,.0f} kg / {diff_pct:+.1f}%）")
    else:
        st.caption(f"先週: {lw_days}日 / {lw_vol:,.0f} kg")
else:
    st.caption("先週: 記録なし")

# ============================================
# 2. トレーニング入力ボタン
# ============================================

if st.button("📝 トレーニングを記録する", use_container_width=True, type="primary"):
    st.switch_page("pages/1_📝_Input.py")

# ============================================
# 3. 週間総合ランキング
# ============================================

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
if is_logged_in():
    if st.button("🚪 ログアウト", use_container_width=True):
        st.session_state.clear()
        st.rerun()
else:
    if st.button("🔐 ログイン", use_container_width=True):
        st.session_state.show_login = True
        st.rerun()

# ログインフォーム表示
if not is_logged_in() and st.session_state.get('show_login'):
    check_password()