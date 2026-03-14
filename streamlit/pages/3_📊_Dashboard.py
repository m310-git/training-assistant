import streamlit as st
import plotly.express as px
from utils.auth import is_logged_in
from utils.bigquery_client import query

st.subheader("📊 ダッシュボード")

# ユーザー切り替え
users = query("SELECT user_id, user_name FROM mart.d_user ORDER BY user_id")

if is_logged_in():
    default_index = users['user_id'].tolist().index(st.session_state.user_id)
else:
    default_index = 0

selected_user = st.selectbox(
    "ユーザー",
    options=users['user_id'].tolist(),
    format_func=lambda x: users[users['user_id']==x]['user_name'].values[0],
    index=default_index
)

# --- KPIカード（複合種目のみ）---
st.subheader("📈 KPI: 週次変化率（目標: ≧1.0%）")

kpi_data = query(f"""
    SELECT
        exercise_name,
        wow_change_pct
    FROM mart.m_progress_curve
    WHERE user_id = '{selected_user}'
      AND is_compound = TRUE
      AND metric_date = (
          SELECT MAX(metric_date)
          FROM mart.m_progress_curve
          WHERE user_id = '{selected_user}'
            AND is_compound = TRUE
      )
""")

if not kpi_data.empty:
    cols = st.columns(len(kpi_data))
    for i, row in kpi_data.iterrows():
        with cols[i]:
            pct = row['wow_change_pct']
            icon = "✅" if pct and pct >= 1.0 else "❌"
            delta_color = "normal" if pct and pct >= 1.0 else "inverse"
            st.metric(
                label=row['exercise_name'],
                value=f"{pct:+.1f}%" if pct else "N/A",
                delta=icon
            )
else:
    st.info("KPIデータがまだありません。トレーニングを記録してください。")

# --- 期間フィルタ ---
period = st.selectbox("期間", ["1ヶ月", "3ヶ月", "6ヶ月", "全期間"])
period_map = {"1ヶ月": 30, "3ヶ月": 90, "6ヶ月": 180, "全期間": 9999}
days = period_map[period]

# --- 進捗グラフ ---
st.subheader("📈 7日間移動平均ボリューム推移")

progress = query(f"""
    SELECT
        metric_date,
        exercise_name,
        volume_7d_ma
    FROM mart.m_progress_curve
    WHERE user_id = '{selected_user}'
      AND is_compound = TRUE
      AND metric_date >= DATE_SUB(CURRENT_DATE('Asia/Tokyo'), INTERVAL {days} DAY)
    ORDER BY metric_date
""")

if not progress.empty:
    fig = px.line(
        progress,
        x='metric_date',
        y='volume_7d_ma',
        color='exercise_name',
        title='7日間移動平均ボリューム',
        labels={
            'metric_date': '日付',
            'volume_7d_ma': 'ボリューム (kg)',
            'exercise_name': '種目'
        }
    )
    fig.update_layout(hovermode='x unified')
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("進捗データがまだありません")

# --- 種目別グラフ ---
st.subheader("📊 種目別ボリューム推移")

all_exercises = query(f"""
    SELECT DISTINCT exercise_name
    FROM mart.m_progress_curve
    WHERE user_id = '{selected_user}'
    ORDER BY exercise_name
""")

if not all_exercises.empty:
    selected_exercise = st.selectbox(
        "種目",
        options=all_exercises['exercise_name'].tolist()
    )

    exercise_data = query(f"""
        SELECT
            metric_date,
            daily_volume,
            volume_7d_ma,
            max_weight,
            total_sets
        FROM mart.m_progress_curve
        WHERE user_id = '{selected_user}'
          AND exercise_name = '{selected_exercise}'
          AND metric_date >= DATE_SUB(CURRENT_DATE('Asia/Tokyo'), INTERVAL {days} DAY)
        ORDER BY metric_date
    """)

    if not exercise_data.empty:
        fig2 = px.line(
            exercise_data,
            x='metric_date',
            y=['daily_volume', 'volume_7d_ma'],
            title=f'{selected_exercise} ボリューム推移',
            labels={
                'metric_date': '日付',
                'value': 'ボリューム (kg)',
                'variable': '指標'
            }
        )
        st.plotly_chart(fig2, use_container_width=True)