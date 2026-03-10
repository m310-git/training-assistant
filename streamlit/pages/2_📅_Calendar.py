import streamlit as st
from datetime import datetime, date, timedelta
import calendar
from utils.auth import check_password
from utils.bigquery_client import query

if not check_password():
    st.stop()

st.title("📅 カレンダー")

# ユーザー切り替え
users = query("SELECT user_id, user_name FROM mart.d_user")
selected_user = st.selectbox(
    "ユーザー",
    options=users['user_id'].tolist(),
    format_func=lambda x: users[users['user_id']==x]['user_name'].values[0],
    index=users['user_id'].tolist().index(st.session_state.user_id)
)

# 月切り替え
today = date.today()
if 'cal_year' not in st.session_state:
    st.session_state.cal_year = today.year
if 'cal_month' not in st.session_state:
    st.session_state.cal_month = today.month

col_prev, col_title, col_next = st.columns([1, 3, 1])
with col_prev:
    if st.button("◀ 前月"):
        if st.session_state.cal_month == 1:
            st.session_state.cal_month = 12
            st.session_state.cal_year -= 1
        else:
            st.session_state.cal_month -= 1
        st.rerun()

with col_title:
    st.subheader(f"{st.session_state.cal_year}年{st.session_state.cal_month}月")

with col_next:
    if st.button("翌月 ▶"):
        if st.session_state.cal_month == 12:
            st.session_state.cal_month = 1
            st.session_state.cal_year += 1
        else:
            st.session_state.cal_month += 1
        st.rerun()

# カレンダーデータ取得（raw から直接集計）
year = st.session_state.cal_year
month = st.session_state.cal_month
first_day = date(year, month, 1)
last_day = date(year, month, calendar.monthrange(year, month)[1])

cal_data = query(f"""
    WITH deduped AS (
        SELECT
            *,
            ROW_NUMBER() OVER (
                PARTITION BY log_id
                ORDER BY updated_at DESC
            ) AS rn
        FROM raw.training_log
        WHERE user_id = '{selected_user}'
          AND training_date BETWEEN '{first_day}' AND '{last_day}'
    ),
    daily_data AS (
        SELECT
            training_date,
            body_part,
            exercise_name,
            weight_kg,
            reps,
            ROUND(weight_kg * reps, 1) AS volume
        FROM deduped
        WHERE rn = 1 AND is_deleted = FALSE
    ),
    exercise_max AS (
        SELECT
            training_date,
            exercise_name,
            MAX(weight_kg) AS max_weight
        FROM daily_data
        GROUP BY training_date, exercise_name
    ),
    exercise_summary AS (
        SELECT
            training_date,
            STRING_AGG(
                CONCAT(exercise_name, ': ', CAST(max_weight AS STRING), 'kg'),
                ' / '
            ) AS exercise_summary
        FROM exercise_max
        GROUP BY training_date
    )
    SELECT
        d.training_date,
        STRING_AGG(DISTINCT d.body_part, ', ') AS body_parts,
        SUM(d.volume) AS total_volume,
        COUNT(DISTINCT d.exercise_name) AS exercise_count,
        es.exercise_summary
    FROM daily_data d
    LEFT JOIN exercise_summary es ON d.training_date = es.training_date
    GROUP BY d.training_date, es.exercise_summary
    ORDER BY d.training_date
""")

# カレンダー表示
cal_dict = {}
if not cal_data.empty:
    for _, row in cal_data.iterrows():
        cal_dict[row['training_date']] = row

# 曜日ヘッダー
day_names = ['月', '火', '水', '木', '金', '土', '日']
header_cols = st.columns(7)
for i, name in enumerate(day_names):
    with header_cols[i]:
        st.markdown(f"**{name}**")

st.markdown("---")

cal = calendar.Calendar(firstweekday=0)
weeks = cal.monthdayscalendar(year, month)

for week in weeks:
    cols = st.columns(7)
    for i, day_num in enumerate(week):
        with cols[i]:
            if day_num == 0:
                st.write("")
            else:
                d = date(year, month, day_num)
                if d in cal_dict:
                    bp = cal_dict[d]['body_parts']
                    st.markdown(f"**{day_num}**")
                    st.markdown(f"🟢{bp}")
                else:
                    st.markdown(f"{day_num}")

# 日付クリックで詳細表示
st.subheader("📋 日付の詳細")
default_date = date(year, month, 1)
if today.year == year and today.month == month:
    default_date = today

selected_date = st.date_input(
    "日付を選択",
    value=default_date,
    min_value=first_day,
    max_value=last_day
)

if selected_date in cal_dict:
    info = cal_dict[selected_date]
    st.markdown(f"**部位:** {info['body_parts']}")
    st.markdown(f"**総ボリューム:** {info['total_volume']:,.1f} kg")
    st.markdown(f"**種目数:** {info['exercise_count']}")

    # 詳細データ取得（raw から直接）
    detail = query(f"""
        SELECT
            exercise_name,
            body_part,
            set_number,
            weight_kg,
            reps,
            rpe,
            ROUND(weight_kg * reps, 1) AS volume
        FROM raw.training_log
        WHERE user_id = '{selected_user}'
          AND training_date = '{selected_date}'
          AND is_deleted = FALSE
        ORDER BY exercise_name, set_number
    """)

    if not detail.empty:
        exercises = detail['exercise_name'].unique()
        for ex in exercises:
            ex_data = detail[detail['exercise_name'] == ex]
            st.markdown(f"**■ {ex}**")
            st.dataframe(
                ex_data[['set_number', 'weight_kg', 'reps', 'rpe']].reset_index(drop=True),
                hide_index=True,
                use_container_width=True
            )

    # 編集ボタン（自分の記録 & 同日のみ）
    if selected_user == st.session_state.user_id:
        is_today = (selected_date == date.today())
        if is_today:
            if st.button("✏️ 編集する"):
                st.session_state.edit_date = selected_date
                st.switch_page("pages/1_📝_Input.py")
        else:
            # 過去日は3時間以内のみ
            created_check = query(f"""
                SELECT MIN(created_at) AS earliest
                FROM raw.training_log
                WHERE user_id = '{selected_user}'
                  AND training_date = '{selected_date}'
                  AND is_deleted = FALSE
            """)
            if not created_check.empty and created_check['earliest'].values[0]:
                import pandas as pd
                earliest = pd.Timestamp(created_check['earliest'].values[0])
                if earliest.tzinfo is None:
                    earliest = earliest.tz_localize('UTC')
                if datetime.now(earliest.tzinfo) < earliest + timedelta(hours=3):
                    if st.button("✏️ 編集する"):
                        st.session_state.edit_date = selected_date
                        st.switch_page("pages/1_📝_Input.py")
else:
    st.info("この日のトレーニング記録はありません")