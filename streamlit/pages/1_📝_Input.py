import streamlit as st
import uuid
import pandas as pd
from datetime import datetime, timedelta, timezone, date
from utils.auth import check_password
from utils.bigquery_client import query, insert_rows
from utils.validators import validate_weight, validate_reps, validate_rpe

if not check_password():
    st.stop()

st.title("📝 トレーニング入力")

# スマホ対応CSS（ページ全体に適用）
st.markdown("""
<style>
/* 全ての横並びブロックを強制 */
div[data-testid="stHorizontalBlock"] {
    flex-wrap: nowrap !important;
    gap: 0.2rem !important;
    overflow: hidden !important;
}
div[data-testid="stHorizontalBlock"] > div {
    min-width: 0 !important;
    overflow: hidden !important;
}
/* ラベルを小さく */
label {
    font-size: 12px !important;
    margin-bottom: 0px !important;
}
/* input を縮小 */
input[type="number"], input[type="text"] {
    font-size: 14px !important;
    padding: 4px 8px !important;
}
div[data-testid="stDateInput"],
div[data-testid="stSelectbox"] {
    min-width: 0 !important;
}
/* metric を小さく */
div[data-testid="stMetric"] label {
    font-size: 11px !important;
}
div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
    font-size: 20px !important;
}
/* selectbox の中身を縮小 */
div[data-testid="stSelectbox"] > div {
    font-size: 13px !important;
}
</style>
""", unsafe_allow_html=True)

user_id = st.session_state.user_id

# --- 日付・部位・種目の選択 ---
training_date = st.date_input("日付", value=datetime.now())

exercises_col1, exercises_col2 = st.columns([2, 5])

body_parts = query("""
    SELECT body_part_id, body_part_name
    FROM mart.d_body_part
    ORDER BY sort_order
""")

with exercises_col1:
    selected_bp = st.selectbox(
        "部位",
        options=body_parts['body_part_id'].tolist(),
        format_func=lambda x: body_parts[body_parts['body_part_id']==x]['body_part_name'].values[0]
    )

exercises = query(f"""
    SELECT exercise_id, exercise_name
    FROM mart.d_exercise
    WHERE body_part_id = '{selected_bp}'
    ORDER BY display_order
""")

with exercises_col2:
    selected_ex = st.selectbox(
        "種目",
        options=exercises['exercise_name'].tolist()
    )

# --- データ取得（表示は後で使う）---
history = query(f"""
    SELECT training_date, set_number, weight_kg, reps, rpe, volume
    FROM mart.fct_training_set
    WHERE user_id = '{user_id}'
      AND exercise_name = '{selected_ex}'
      AND training_date < '{training_date}'
    ORDER BY training_date DESC, set_number
    LIMIT 30
""")

# --- 提案の表示 ---
st.subheader("💡 今回の提案")

suggestion = None
try:
    suggestion = query(f"""
        SELECT set_number, suggested_weight_kg, suggested_reps, suggested_volume
        FROM mart.m_ml_suggestion
        WHERE user_id = '{user_id}'
          AND exercise_name = '{selected_ex}'
        ORDER BY set_number
    """)
except Exception:
    suggestion = None

if suggestion is not None and not suggestion.empty:
    st.markdown("🤖 **AIモデルによる提案**")
    st.dataframe(suggestion.reset_index(drop=True), hide_index=True, use_container_width=True)
    total_suggested = suggestion['suggested_volume'].sum()
    st.metric("提案通りの総負荷量", f"{total_suggested:,.1f} kg")
else:
    if not history.empty:
        latest_date = history['training_date'].max()
        latest = history[history['training_date'] == latest_date]
        st.markdown("📈 **過去実績ベースの提案**")
        fallback_data = []
        for _, row in latest.iterrows():
            sw = round(row['weight_kg'] * 1.025, 1)
            sr = int(row['reps'])
            fallback_data.append({
                'set_number': int(row['set_number']),
                'suggested_weight_kg': sw,
                'suggested_reps': sr,
                'suggested_volume': round(sw * sr, 1)
            })
        fb_df = pd.DataFrame(fallback_data)
        st.dataframe(fb_df, hide_index=True, use_container_width=True)
        st.info("ℹ️ データが蓄積されるとAIモデルによる提案に切り替わります")
    else:
        st.info("提案を表示するには過去の記録が必要です")

# --- 論理削除ヘルパー ---
def soft_delete_log(log_id):
    try:
        query(f"""
            UPDATE raw.training_log
            SET is_deleted = TRUE, updated_at = CURRENT_TIMESTAMP()
            WHERE log_id = '{log_id}'
        """)
    except Exception:
        original = query(f"""
            SELECT * FROM raw.training_log
            WHERE log_id = '{log_id}'
            ORDER BY updated_at DESC
            LIMIT 1
        """)
        if not original.empty:
            row = original.iloc[0]
            now = datetime.now(timezone.utc).isoformat()
            delete_row = {
                'log_id': row['log_id'],
                'user_id': row['user_id'],
                'exercise_name': row['exercise_name'],
                'body_part': row['body_part'],
                'training_date': str(row['training_date']),
                'set_number': int(row['set_number']),
                'weight_kg': float(row['weight_kg']),
                'reps': int(row['reps']),
                'rpe': float(row['rpe']) if row['rpe'] else None,
                'memo': row['memo'] or '',
                'input_source': 'streamlit',
                'created_at': row['created_at'].isoformat() if hasattr(row['created_at'], 'isoformat') else str(row['created_at']),
                'updated_at': now,
                'is_deleted': True
            }
            insert_rows('training-assistant-prod.raw.training_log', [delete_row])

# --- セット入力 ---
st.subheader("✏️ セット入力")

# 種目が変わったらセット状態をリセット
restore_key = f"{training_date}_{selected_ex}"
if st.session_state.get('restore_key') != restore_key:
    st.session_state.sets = None
    st.session_state.restored = False
    st.session_state.restore_key = restore_key

existing = query(f"""
    SELECT log_id, set_number, weight_kg, reps, rpe, memo, created_at
    FROM raw.training_log
    WHERE user_id = '{user_id}'
      AND exercise_name = '{selected_ex}'
      AND training_date = '{training_date}'
      AND is_deleted = FALSE
    ORDER BY set_number
""")

is_today = (training_date == date.today())

if st.session_state.get('sets') is None:
    if not existing.empty:
        st.session_state.sets = []
        for _, row in existing.iterrows():
            created = row['created_at']
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if is_today:
                editable = True
            else:
                editable = datetime.now(timezone.utc) < created + timedelta(hours=3)
            st.session_state.sets.append({
                'log_id': row['log_id'],
                'weight': float(row['weight_kg']),
                'reps': int(row['reps']),
                'rpe': float(row['rpe']) if row['rpe'] else None,
                'memo': row['memo'] or '',
                'saved': True,
                'editable': editable
            })
        st.session_state.restored = True
    else:
        st.session_state.sets = [
            {'weight': None, 'reps': None, 'rpe': None, 'memo': '', 'saved': False}
            for _ in range(5)
        ]

if not existing.empty and st.session_state.get('restored'):
    saved_count = len([s for s in st.session_state.sets if s.get('saved')])
    st.success(f"✅ 本日の記録を復元しました（{saved_count}セット）。セットの追加・編集が可能です。")

# セット入力フォーム
total_volume = 0.0

for i, s in enumerate(st.session_state.sets):
    set_num = i + 1
    editable = s.get('editable', True)
    status = "✅" if s['saved'] else "⬜"

    st.markdown(f"**{set_num}** {status}")

    col1, col2 = st.columns(2)
    with col1:
        w = st.number_input(
            "kg", min_value=0.0, max_value=500.0, step=0.5,
            value=s['weight'] if s['weight'] is not None else 0.0,
            key=f"w_{i}", disabled=not editable
        )
    with col2:
        r = st.number_input(
            "回", min_value=1, max_value=100, step=1,
            value=s['reps'] if s['reps'] is not None else 1,
            key=f"r_{i}", disabled=not editable
        )

    memo = st.text_input(
        "メモ", value=s.get('memo', ''), key=f"memo_{i}",
        max_chars=200, disabled=not editable
    )

    if w and r:
        total_volume += w * r

    if w and r and w > 0 and r > 0 and not s['saved'] and editable:
        valid_w, _ = validate_weight(w)
        valid_r, _ = validate_reps(r)

        if valid_w and valid_r:
            log_id = s.get('log_id', str(uuid.uuid4()))
            now = datetime.now(timezone.utc).isoformat()

            row = {
                'log_id': log_id,
                'user_id': user_id,
                'exercise_name': selected_ex,
                'body_part': selected_bp,
                'training_date': str(training_date),
                'set_number': set_num,
                'weight_kg': float(w),
                'reps': int(r),
                'rpe': None,
                'memo': memo,
                'input_source': 'streamlit',
                'created_at': now,
                'updated_at': now,
                'is_deleted': False
            }

            try:
                insert_rows('training-assistant-prod.raw.training_log', [row])
                st.session_state.sets[i]['saved'] = True
                st.session_state.sets[i]['log_id'] = log_id
            except Exception as e:
                st.error(f"保存エラー: {e}")

# 総負荷量の表示
st.markdown("---")
col_vol1, col_vol2 = st.columns(2)
with col_vol1:
    st.metric("📊 現在の総負荷量", f"{total_volume:,.1f} kg")
with col_vol2:
    if not history.empty:
        latest_date = history['training_date'].max()
        prev_vol = history[history['training_date'] == latest_date]['volume'].sum()
        diff = total_volume - prev_vol
        diff_pct = (diff / prev_vol * 100) if prev_vol > 0 else 0
        st.metric("前回との差分", f"{diff:+,.1f} kg ({diff_pct:+.1f}%)")

# セット追加・削除ボタン
col_btn1, col_btn2, col_btn3 = st.columns(3)
with col_btn1:
    if st.button("＋ 追加", use_container_width=True):
        if len(st.session_state.sets) < 20:
            st.session_state.sets.append({
                'weight': None, 'reps': None, 'rpe': None,
                'memo': '', 'saved': False
            })
            st.rerun()
        else:
            st.warning("上限（20）です")

with col_btn2:
    if st.button("🗑 末尾削除", use_container_width=True):
        if len(st.session_state.sets) > 1:
            last = st.session_state.sets[-1]
            if last.get('log_id'):
                soft_delete_log(last['log_id'])
            st.session_state.sets.pop()
            st.rerun()

with col_btn3:
    saved_sets = [s for s in st.session_state.sets if s.get('log_id')]
    if saved_sets:
        if st.button("🗑 全削除", use_container_width=True, type="secondary"):
            st.session_state.confirm_delete_all = True

# --- 直近3回の実績（一番下に表示）---
st.markdown("---")
st.subheader("📋 直近3回の実績")

if not history.empty:
    dates = history['training_date'].unique()[:3]
    for d in dates:
        day_data = history[history['training_date'] == d]
        total_vol = day_data['volume'].sum()
        with st.expander(f"■ {d}　総負荷量: {total_vol:,.1f} kg"):
            st.dataframe(
                day_data[['set_number', 'weight_kg', 'reps', 'rpe']].reset_index(drop=True),
                hide_index=True,
                use_container_width=True
            )
else:
    st.info("この種目の記録はまだありません")