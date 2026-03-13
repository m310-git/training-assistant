import streamlit as st
from datetime import datetime, timedelta
from utils.auth import check_password
from utils.bigquery_client import query

if not check_password():
    st.stop()

st.subheader("👥 ソーシャル")

# --- 記録更新フィード（mart参照のまま：日次更新でOK）---
st.subheader("🔔 記録更新フィード")

try:
    records = query("""
        SELECT
            user_name, exercise_name, record_type,
            record_value, previous_value, achieved_date
        FROM mart.m_personal_record
        WHERE is_new = TRUE
        ORDER BY achieved_date DESC
    """)
except Exception:
    records = None

if records is not None and not records.empty:
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

# --- 他ユーザーの記録（raw から直接参照）---
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

# 部位フィルタ（raw の body_part は body_part_id 形式なので変換）
bp_filter = ""
if selected_bp != "全部位":
    bp_id = query(f"""
        SELECT body_part_id FROM mart.d_body_part
        WHERE body_part_name = '{selected_bp}'
    """)
    if not bp_id.empty:
        bp_filter = f"AND body_part = '{bp_id['body_part_id'].iloc[0]}'"

detail = query(f"""
    WITH deduped AS (
        SELECT
            *,
            ROW_NUMBER() OVER (
                PARTITION BY log_id
                ORDER BY updated_at DESC
            ) AS rn
        FROM raw.training_log
        WHERE user_id = '{selected_user}'
          AND training_date = '{selected_date}'
          {bp_filter}
    )
    SELECT
        exercise_name,
        body_part,
        set_number,
        weight_kg,
        reps,
        rpe,
        ROUND(weight_kg * reps, 1) AS volume
    FROM deduped
    WHERE rn = 1 AND is_deleted = FALSE
    ORDER BY exercise_name, set_number
""")

if not detail.empty:
    # body_part_id → 表示名の変換用
    bp_names = query("SELECT body_part_id, body_part_name FROM mart.d_body_part")
    bp_map = dict(zip(bp_names['body_part_id'], bp_names['body_part_name']))

    exercises = detail['exercise_name'].unique()
    for ex in exercises:
        ex_data = detail[detail['exercise_name'] == ex]
        bp_name = bp_map.get(ex_data['body_part'].iloc[0], ex_data['body_part'].iloc[0])
        st.markdown(f"**■ {ex}（{bp_name}）**")
        st.dataframe(
            ex_data[['set_number', 'weight_kg', 'reps', 'rpe']].reset_index(drop=True),
            hide_index=True,
            use_container_width=True
        )
else:
    st.info("この日のトレーニング記録はありません")