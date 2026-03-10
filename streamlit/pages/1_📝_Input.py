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

user_id = st.session_state.user_id

# --- 日付・部位・種目の選択 ---
col1, col2, col3 = st.columns(3)

with col1:
    training_date = st.date_input("日付", value=datetime.now())

# 部位一覧を取得
body_parts = query("""
    SELECT body_part_id, body_part_name
    FROM mart.d_body_part
    ORDER BY sort_order
""")

with col2:
    selected_bp = st.selectbox(
        "部位",
        options=body_parts['body_part_id'].tolist(),
        format_func=lambda x: body_parts[body_parts['body_part_id']==x]['body_part_name'].values[0]
    )

# 選択した部位の種目一覧を取得
exercises = query(f"""
    SELECT exercise_id, exercise_name
    FROM mart.d_exercise
    WHERE body_part_id = '{selected_bp}'
    ORDER BY display_order
""")

with col3:
    selected_ex = st.selectbox(
        "種目",
        options=exercises['exercise_name'].tolist()
    )

# --- 過去実績の表示（本日分を除外）---
st.subheader("📋 直近3回の実績")
history = query(f"""
    SELECT training_date, set_number, weight_kg, reps, rpe, volume
    FROM mart.fct_training_set
    WHERE user_id = '{user_id}'
      AND exercise_name = '{selected_ex}'
      AND training_date < '{training_date}'
    ORDER BY training_date DESC, set_number
    LIMIT 30
""")

if not history.empty:
    dates = history['training_date'].unique()[:3]
    for d in dates:
        day_data = history[history['training_date'] == d]
        total_vol = day_data['volume'].sum()
        st.markdown(f"**■ {d}　総負荷量: {total_vol:,.1f} kg**")
        st.dataframe(
            day_data[['set_number', 'weight_kg', 'reps', 'rpe']].reset_index(drop=True),
            hide_index=True,
            use_container_width=True
        )
else:
    st.info("この種目の記録はまだありません")

# --- 提案の表示 ---
st.subheader("💡 今回の提案")

# MLの提案を取得（テーブルが存在しない場合はスキップ）
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
    # フォールバック: 直近の記録から+2.5%
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

# --- セット入力 ---
st.subheader("✏️ セット入力")

# 種目が変わったらセット状態をリセット
restore_key = f"{training_date}_{selected_ex}"
if st.session_state.get('restore_key') != restore_key:
    st.session_state.sets = None
    st.session_state.restored = False
    st.session_state.restore_key = restore_key

# 当日の既存記録を取得
existing = query(f"""
    SELECT log_id, set_number, weight_kg, reps, rpe, memo, created_at
    FROM raw.training_log
    WHERE user_id = '{user_id}'
      AND exercise_name = '{selected_ex}'
      AND training_date = '{training_date}'
      AND is_deleted = FALSE
    ORDER BY set_number
""")

# 同日中かどうかを判定
is_today = (training_date == date.today())

# セット状態の初期化・復元
if st.session_state.get('sets') is None:
    if not existing.empty:
        # 既存記録を復元
        st.session_state.sets = []
        for _, row in existing.iterrows():
            created = row['created_at']
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)

            # 同日中は常に編集可能、翌日以降は3時間制限
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
        # 新規：空のセットを5つ用意
        st.session_state.sets = [
            {'weight': None, 'reps': None, 'rpe': None, 'memo': '', 'saved': False}
            for _ in range(5)
        ]

# 復元メッセージ
if not existing.empty and st.session_state.get('restored'):
    saved_count = len([s for s in st.session_state.sets if s.get('saved')])
    st.success(f"✅ 本日の記録を復元しました（{saved_count}セット）。セットの追加・編集が可能です。")

# セット入力フォーム
total_volume = 0.0

for i, s in enumerate(st.session_state.sets):
    set_num = i + 1
    cols = st.columns([1, 2, 2, 2, 3, 1])

    with cols[0]:
        st.markdown(f"**{set_num}**")

    editable = s.get('editable', True)

    with cols[1]:
        w = st.number_input(
            "重量(kg)", min_value=0.0, max_value=500.0, step=0.5,
            value=s['weight'] if s['weight'] is not None else 0.0,
            key=f"w_{i}", disabled=not editable
        )

    with cols[2]:
        r = st.number_input(
            "回数", min_value=1, max_value=100, step=1,
            value=s['reps'] if s['reps'] is not None else 1,
            key=f"r_{i}", disabled=not editable
        )

    with cols[3]:
        rpe = st.number_input(
            "RPE", min_value=6.0, max_value=10.0, step=0.5,
            value=s['rpe'] if s['rpe'] is not None else 8.0,
            key=f"rpe_{i}", disabled=not editable
        )

    with cols[4]:
        memo = st.text_input(
            "メモ", value=s['memo'], key=f"memo_{i}",
            max_chars=200, disabled=not editable
        )

    with cols[5]:
        if s['saved']:
            st.markdown("✅")
        else:
            st.markdown("⬜")

    # ボリューム計算
    if w and r:
        total_volume += w * r

    # 自動保存判定
    if w and r and w > 0 and r > 0 and not s['saved'] and editable:
        valid_w, _ = validate_weight(w)
        valid_r, _ = validate_reps(r)
        valid_rpe, _ = validate_rpe(rpe)

        if valid_w and valid_r and valid_rpe:
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
                'rpe': float(rpe) if rpe else None,
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
col_btn1, col_btn2 = st.columns(2)
with col_btn1:
    if st.button("＋ セット追加"):
        if len(st.session_state.sets) < 20:
            st.session_state.sets.append({
                'weight': None, 'reps': None, 'rpe': None,
                'memo': '', 'saved': False
            })
            st.rerun()
        else:
            st.warning("セット数の上限（20）に達しました")

with col_btn2:
    if st.button("🗑 最終セット削除"):
        if len(st.session_state.sets) > 1:
            last = st.session_state.sets[-1]
            if last.get('log_id'):
                # 論理削除
                query(f"""
                    UPDATE raw.training_log
                    SET is_deleted = TRUE, updated_at = CURRENT_TIMESTAMP()
                    WHERE log_id = '{last["log_id"]}'
                """)
            st.session_state.sets.pop()
            st.rerun()