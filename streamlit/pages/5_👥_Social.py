import streamlit as st
from datetime import datetime, timedelta
from utils.auth import check_password
from utils.bigquery_client import query

if not check_password():
    st.stop()

st.title("👥 ソーシャル")

# --- 記録更新フィード ---
st.subheader("🔔 記録更新フィード")

records = query("""
    SELECT
        user_name, exercise_name, record_type,
        record_value, previous_value, achieved_date
    FROM mart.m_personal_record
    WHERE is_new = TRUE
    ORDER BY achieved_date DESC
""")

if not records.empty:
    for _, row in records.iterrows():
        if row['record_type'] == 'max_weight':
            icon = "🎉"
            label = "最高重量"
            unit = "kg"
        else:
            icon = "💪"
            label = "最高ボリューム"
            unit = "kg"

        prev = f"{row['previous_value']:,.1f}" if row['previous_value'] else "---"
        st.markdown(
            f"{icon} **{row['achieved_date']}** {row['user_name']}が"
            f"**{row['exercise_name']}**の{label}を更新！ "
            f"{prev} → **{row['record_value']:,.1f}** {unit}"
        )
else:
    st.info("直近7日間の記録更新はありません")

# --- 他ユーザーの記録 ---
st.markdown("---")
st.subheader("👤 他ユーザーの記録")

users = query("SELECT user_id, user_name FROM mart.d_user")

col1, col2, col3 = st.columns(3)
with col1:
    selected_user = st.selectbox(
        "ユーザー",
        options=users['user_id'].tolist(),
        format_func=lambda x: users[users['user_id']==x]['user_name'].values[0]
    )
with col2:
    selected_date = st.date_input("日付", value=datetime.now())
with col3:
    bp_options = ["全部位"] + query(
        "SELECT body_part_name FROM mart.d_body_part ORDER BY sort_order"
    )['body_part_name'].tolist()
    selected_bp = st.selectbox("部位", options=bp_options)

bp_filter = ""
if selected_bp != "全部位":
    bp_filter = f"AND body_part_name = '{selected_bp}'"

detail = query(f"""
    SELECT exercise_name, body_part_name, set_number, weight_kg, reps, rpe, volume
    FROM mart.fct_training_set
    WHERE user_id = '{selected_user}'
      AND training_date = '{selected_date}'
      {bp_filter}
    ORDER BY exercise_name, set_number
""")

if not detail.empty:
    exercises = detail['exercise_name'].unique()
    for ex in exercises:
        ex_data = detail[detail['exercise_name'] == ex]
        bp_name = ex_data['body_part_name'].iloc[0]
        st.markdown(f"**■ {ex}（{bp_name}）**")
        st.dataframe(
            ex_data[['set_number', 'weight_kg', 'reps', 'rpe']].reset_index(drop=True),
            hide_index=True,
            use_container_width=True
        )
else:
    st.info("この日のトレーニング記録はありません")