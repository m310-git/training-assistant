import streamlit as st
import uuid
import pandas as pd
from datetime import datetime, timedelta, timezone, date
from utils.auth import is_logged_in, require_login_for_action
from utils.bigquery_client import query
from utils.firestore_client import (
    get_training_log,
    save_training_log,
    soft_delete_set,
    soft_delete_training_log,
)

st.subheader("📝 トレーニング入力")

# user_id の取得部分
if is_logged_in():
    user_id = st.session_state.user_id
else:
    user_id = 'user_001'  # 閲覧用デフォルト

if not is_logged_in():
    st.info("💡 データの保存にはログインが必要です")

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
/* ===== セット入力の圧縮 ===== */
/* +/- ボタンを非表示 */
div[data-testid="stNumberInput"] [data-testid="stNumberInputStepUp"],
div[data-testid="stNumberInput"] [data-testid="stNumberInputStepDown"] {
    display: none !important;
}
/* ボタン非表示後にinput枠を幅いっぱいに広げる */
div[data-testid="stNumberInput"] > div > div > div {
    width: 100% !important;
}
div[data-testid="stNumberInput"] input {
    width: 100% !important;
    text-align: left !important;
}
/* ウィジェット間の縦余白を削減 */
div[data-testid="stNumberInput"] {
    margin-top: -0.4rem !important;
    margin-bottom: -0.4rem !important;
}
</style>
""", unsafe_allow_html=True)

if is_logged_in():
    user_id = st.session_state.user_id
    user_name = st.session_state.user_name
else:
    users = query("SELECT user_id, user_name FROM mart.d_user ORDER BY user_id")
    user_id = st.selectbox(
        "表示するユーザー",
        options=users['user_id'].tolist(),
        format_func=lambda x: users[users['user_id']==x]['user_name'].values[0]
    )
    user_name = users[users['user_id']==user_id]['user_name'].values[0]

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

# 種目一覧を取得（exercise_id ベース）
exercises = query(f"""
    SELECT exercise_id, exercise_name
    FROM raw.exercise_master
    WHERE body_part_id = '{selected_bp}'
      AND is_active = TRUE
    ORDER BY display_order
""")

with exercises_col2:
    # 内部値は exercise_id、表示は exercise_name
    selected_ex_id = st.selectbox(
        "種目",
        options=exercises['exercise_id'].tolist(),
        format_func=lambda x: exercises[exercises['exercise_id']==x]['exercise_name'].values[0]
    )

# 選択中の exercise_name を取得（表示・BigQuery参照用）
selected_ex_name = exercises[exercises['exercise_id']==selected_ex_id]['exercise_name'].values[0]
# 選択中の body_part_name を取得（Firestore保存用）
selected_bp_name = body_parts[body_parts['body_part_id']==selected_bp]['body_part_name'].values[0]

# --- データ取得（表示は後で使う）---
history = query(f"""
    SELECT training_date, set_number, weight_kg, reps, rpe, volume, IFNULL(memo, '') AS memo
    FROM mart.fct_training_set
    WHERE user_id = '{user_id}'
      AND exercise_id = '{selected_ex_id}'
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
          AND exercise_id = '{selected_ex_id}'
        ORDER BY set_number
    """)
except Exception:
    suggestion = None

if suggestion is not None and not suggestion.empty:
    st.markdown("🤖 **AIモデルによる提案**")
    # スマホ対応：カラム名を短縮して表示
    display_df = suggestion.rename(columns={
        'set_number': 'Set',
        'suggested_weight_kg': 'kg',
        'suggested_reps': '回',
        'suggested_volume': '総量'
    })
    st.table(display_df
             .reset_index(drop=True)
             .set_index('Set')
             .style.format({'kg': '{:.2f}', '総量': '{:.2f}'})
    )
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
                'Set': int(row['set_number']),
                'kg': sw,
                '回': sr,
                '総量': round(sw * sr, 1)
            })
        fb_df = pd.DataFrame(fallback_data)
        st.table(fb_df)
        st.info("ℹ️ データが蓄積されるとAIモデルによる提案に切り替わります")
    else:
        st.info("提案を表示するには過去の記録が必要です")

# --- セット入力 ---
st.subheader("✏️ セット入力")

# 注記: Firestore/BigQuery同期について
st.info("""
ℹ️ **データ保存について**
- 保存データは Firestore に即時反映されます
- 履歴・提案・直近実績などの分析系表示は BigQuery 同期後に更新されます
""")

# 部位・種目が変わったらセット状態をリセット（exercise_id ベース）
restore_key = f"{training_date}_{selected_bp}_{selected_ex_id}"
if st.session_state.get('restore_key') != restore_key:
    # 全てのウィジェット状態をクリア
    keys_to_delete = [k for k in list(st.session_state.keys()) 
                      if k.startswith(('w_', 'r_', 'memo_', 'rpe_'))]
    for k in keys_to_delete:
        del st.session_state[k]
    
    st.session_state.sets = None
    st.session_state.restored = False
    st.session_state.confirm_delete_all = False
    st.session_state.restore_key = restore_key

# Firestore から当日の既存記録を取得
existing_doc = get_training_log(user_id, str(training_date), selected_ex_id)

is_today = (training_date == date.today())

# Firestore のセット数とセッションが異なる場合はリセット
fs_active_sets = []
if existing_doc:
    fs_active_sets = [s for s in existing_doc.get("sets", []) if not s.get("is_deleted", False)]
current_saved = len([s for s in (st.session_state.get('sets') or []) if s.get('saved')])
fs_count = len(fs_active_sets)
if st.session_state.get('sets') is not None and current_saved != fs_count and fs_count > 0:
    st.session_state.sets = None
    st.session_state.restored = False

# セット状態の初期化・復元（Firestore から）
if st.session_state.get('sets') is None:
    # ウィジェット状態を再度クリア（確実に）
    keys_to_delete = [k for k in list(st.session_state.keys()) 
                      if k.startswith(('w_', 'r_', 'memo_', 'rpe_'))]
    for k in keys_to_delete:
        del st.session_state[k]

    if fs_active_sets:
        st.session_state.sets = []
        # editable_until で編集可否を判定
        editable_until_str = existing_doc.get("editable_until")
        for s in fs_active_sets:
            if is_today:
                editable = True
            elif editable_until_str:
                try:
                    editable_until_dt = datetime.fromisoformat(editable_until_str)
                    editable = datetime.now(timezone.utc) < editable_until_dt
                except (ValueError, TypeError):
                    editable = False
            else:
                editable = False
            st.session_state.sets.append({
                'set_id': s.get('set_id', str(uuid.uuid4())),
                'weight': float(s['weight_kg']),
                'reps': int(s['reps']),
                'rpe': s.get('rpe'),
                'memo': s.get('memo', ''),
                'saved': True,
                'editable': editable,
                'created_at': s.get('created_at'),  # created_at をそのまま使用
            })
        st.session_state.restored = True
    else:
        # 新規入力：空のセットを5つ用意
        st.session_state.sets = [
            {'weight': None, 'reps': None, 'rpe': None, 'memo': '', 'saved': False}
            for _ in range(5)
        ]

if fs_active_sets and st.session_state.get('restored'):
    saved_count = len([s for s in st.session_state.sets if s.get('saved')])
    st.success(f"✅ 本日の記録を復元しました（{saved_count}セット）。セットの追加・編集が可能です。")

# ===== セット入力フォーム（st.form 版）=====
total_volume = 0.0
key_prefix = f"{selected_bp}_{selected_ex_id}_{training_date}"

with st.form("set_input_form"):
    for i, s in enumerate(st.session_state.sets):
        set_num = i + 1
        editable = s.get('editable', True)
        status = "✅" if s['saved'] else ""

        c0, c1, c2, c3 = st.columns([1, 3, 2, 4])
        with c0:
            st.markdown(f"{set_num}{status}")
        with c1:
            st.number_input(
                "kg", min_value=0.0, max_value=500.0, step=0.5,
                value=s['weight'] if s['weight'] is not None else 0.0,
                key=f"w_{key_prefix}_{i}", disabled=not editable,
                label_visibility="visible" if i == 0 else "collapsed"
            )
        with c2:
            st.number_input(
                "rep", min_value=0, max_value=100, step=1,
                value=s['reps'] if s['reps'] is not None else 0,
                key=f"r_{key_prefix}_{i}", disabled=not editable,
                label_visibility="visible" if i == 0 else "collapsed"
            )
        with c3:
            st.text_input(
                "memo", value=s.get('memo', ''),
                key=f"memo_{key_prefix}_{i}",
                max_chars=200, disabled=not editable,
                label_visibility="visible" if i == 0 else "collapsed"
            )

    # 保存ボタン（form 内）
    submitted = st.form_submit_button("💾 保存", use_container_width=True, type="primary")

# form 外で volume を集計
for i, s in enumerate(st.session_state.sets):
    w_val = st.session_state.get(f"w_{key_prefix}_{i}", 0.0)
    r_val = st.session_state.get(f"r_{key_prefix}_{i}", 0)
    if w_val and r_val:
        total_volume += w_val * r_val

# 保存処理（form submit 後）
if submitted:
    require_login_for_action()

    now = datetime.now(timezone.utc).isoformat()
    new_sets = []
    has_valid_set = False

    for i, s in enumerate(st.session_state.sets):
        w_val = st.session_state.get(f"w_{key_prefix}_{i}")
        r_val = st.session_state.get(f"r_{key_prefix}_{i}")
        memo_val = st.session_state.get(f"memo_{key_prefix}_{i}", '')

        if w_val is None or r_val is None or w_val <= 0 or r_val <= 0:
            continue

        has_valid_set = True
        set_id = s.get('set_id', str(uuid.uuid4()))

        # 既存セットは created_at を維持、新規セットは now
        created_at = s.get('created_at') if s.get('saved') else now

        new_sets.append({
            "set_id": set_id,
            "set_number": i + 1,
            "weight_kg": float(w_val),
            "reps": int(r_val),
            "rpe": None,
            "memo": memo_val if memo_val else "",
            "is_deleted": False,
            "created_at": created_at,
            "updated_at": now,
        })

    if has_valid_set:
        # 既存の論理削除済みセットも保持する
        if existing_doc:
            deleted_sets = [s for s in existing_doc.get("sets", []) if s.get("is_deleted", False)]
            new_sets = new_sets + deleted_sets

        success = save_training_log(
            user_id=user_id,
            user_name=user_name if is_logged_in() else "",
            training_date=str(training_date),
            body_part_id=selected_bp,
            body_part_name=selected_bp_name,
            exercise_id=selected_ex_id,
            exercise_name=selected_ex_name,
            sets=new_sets,
        )
        if success:
            # session_state を更新
            for i, ns in enumerate(
                [s for s in new_sets if not s.get("is_deleted", False)]
            ):
                if i < len(st.session_state.sets):
                    st.session_state.sets[i]['saved'] = True
                    st.session_state.sets[i]['set_id'] = ns['set_id']
                    st.session_state.sets[i]['weight'] = ns['weight_kg']
                    st.session_state.sets[i]['reps'] = ns['reps']
                    st.session_state.sets[i]['memo'] = ns['memo']
            active_count = len([s for s in new_sets if not s.get("is_deleted", False)])
            st.success(f"✅ {active_count}セット保存しました")
            st.rerun()
    else:
        st.info("変更はありません")

# 総負荷量の表示
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

# セット追加・削除ボタン（form 外）
col_btn1, col_btn2, col_btn3 = st.columns(3)
with col_btn1:
    if st.button("＋ 追加", use_container_width=True):
        require_login_for_action()
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
        require_login_for_action()
        if len(st.session_state.sets) > 1:
            last = st.session_state.sets[-1]
            # Firestore に保存済みのセットなら論理削除
            if last.get('set_id') and last.get('saved'):
                soft_delete_set(user_id, str(training_date), selected_ex_id, last['set_id'])
            st.session_state.sets.pop()
            st.rerun()

with col_btn3:
    saved_sets = [s for s in st.session_state.sets if s.get('set_id') and s.get('saved')]
    if saved_sets:
        if st.button("🗑 全削除", use_container_width=True, type="secondary"):
            require_login_for_action()
            # Firestore ドキュメント全体を論理削除
            soft_delete_training_log(user_id, str(training_date), selected_ex_id)
            # ウィジェットキーをクリア
            keys_to_delete = [k for k in list(st.session_state.keys())
                              if k.startswith(('w_', 'r_', 'memo_', 'rpe_'))]
            for k in keys_to_delete:
                del st.session_state[k]
            st.session_state.sets = None
            st.session_state.restored = False
            st.session_state.restore_key = None
            st.rerun()

# --- 直近3回の実績（一番下に表示）---
st.subheader("📋 直近3回の実績")

if not history.empty:
    dates = history['training_date'].unique()[:3]
    for d in dates:
        day_data = history[history['training_date'] == d]
        total_vol = day_data['volume'].sum()
        with st.expander(f"■ {d}　総負荷量: {total_vol:,.1f} kg"):
            st.table(
                day_data[['set_number', 'weight_kg', 'reps', 'memo']]
                .rename(columns={'set_number': 'set', 'weight_kg': 'kg'})
                .reset_index(drop=True)
                .set_index('set')
                .style.format({'kg': '{:.2f}', 'reps': '{:.0f}'})
            )
else:
    st.info("この種目の記録はまだありません")