import streamlit as st
from utils.auth import check_password
from utils.bigquery_client import query

if not check_password():
    st.stop()

st.title("🏆 ランキング")

# 期間タブ
tab_weekly, tab_monthly, tab_alltime = st.tabs(["週間", "月間", "全期間"])

rank_icons = {1: "🥇", 2: "🥈", 3: "🥉"}
change_icons = {"UP": "↑", "DOWN": "↓", "SAME": "→", "NEW": "NEW"}

# --- 週間ランキング ---
with tab_weekly:
    weekly = query("""
        SELECT user_name, total_volume, rank, rank_change, prev_rank, week_start, week_end
        FROM mart.m_ranking_weekly
        WHERE week_start = (SELECT MAX(week_start) FROM mart.m_ranking_weekly)
        ORDER BY rank
    """)

    if not weekly.empty:
        ws = weekly['week_start'].iloc[0]
        we = weekly['week_end'].iloc[0]
        st.subheader(f"総合ランキング（{ws}〜{we}）")

        for _, row in weekly.iterrows():
            icon = rank_icons.get(row['rank'], f"{row['rank']}位")
            change = change_icons.get(row['rank_change'], "")
            prev = f"(前回{int(row['prev_rank'])}位)" if row['prev_rank'] else ""
            st.markdown(
                f"{icon} **{row['user_name']}**: {row['total_volume']:,.0f} kg  "
                f"{change} {prev}"
            )
    else:
        st.info("週間ランキングデータがまだありません")

# --- 月間ランキング ---
with tab_monthly:
    monthly = query("""
        SELECT user_name, total_volume, rank, rank_change, prev_rank, month
        FROM mart.m_ranking_monthly
        WHERE month = (SELECT MAX(month) FROM mart.m_ranking_monthly)
        ORDER BY rank
    """)

    if not monthly.empty:
        m = monthly['month'].iloc[0]
        st.subheader(f"総合ランキング（{m.strftime('%Y年%m月')}）")

        for _, row in monthly.iterrows():
            icon = rank_icons.get(row['rank'], f"{row['rank']}位")
            change = change_icons.get(row['rank_change'], "")
            prev = f"(前回{int(row['prev_rank'])}位)" if row['prev_rank'] else ""
            st.markdown(
                f"{icon} **{row['user_name']}**: {row['total_volume']:,.0f} kg  "
                f"{change} {prev}"
            )
    else:
        st.info("月間ランキングデータがまだありません")

# --- 全期間ランキング ---
with tab_alltime:
    alltime = query("""
        SELECT user_name, total_volume, rank
        FROM mart.m_ranking_alltime
        ORDER BY rank
    """)

    if not alltime.empty:
        st.subheader("全期間ランキング")
        for _, row in alltime.iterrows():
            icon = rank_icons.get(row['rank'], f"{row['rank']}位")
            st.markdown(
                f"{icon} **{row['user_name']}**: {row['total_volume']:,.0f} kg"
            )
    else:
        st.info("ランキングデータがまだありません")

# --- 部位別ランキング ---
st.markdown("---")
st.subheader("部位別ランキング")

body_parts = query("SELECT body_part_id, body_part_name FROM mart.d_body_part ORDER BY sort_order")
selected_bp = st.selectbox(
    "部位",
    options=body_parts['body_part_id'].tolist(),
    format_func=lambda x: body_parts[body_parts['body_part_id']==x]['body_part_name'].values[0]
)

bp_period = st.radio("期間", ["weekly", "monthly", "alltime"], horizontal=True,
                     format_func=lambda x: {"weekly": "週間", "monthly": "月間", "alltime": "全期間"}[x])

bp_ranking = query(f"""
    SELECT user_name, total_volume, rank
    FROM mart.m_ranking_bodypart
    WHERE body_part_id = '{selected_bp}'
      AND period_type = '{bp_period}'
      AND (period_start = (
          SELECT MAX(period_start)
          FROM mart.m_ranking_bodypart
          WHERE body_part_id = '{selected_bp}'
            AND period_type = '{bp_period}'
      ) OR period_start IS NULL)
    ORDER BY rank
""")

if not bp_ranking.empty:
    for _, row in bp_ranking.iterrows():
        icon = rank_icons.get(row['rank'], f"{row['rank']}位")
        st.markdown(f"{icon} **{row['user_name']}**: {row['total_volume']:,.0f} kg")
else:
    st.info("この部位のランキングデータがまだありません")