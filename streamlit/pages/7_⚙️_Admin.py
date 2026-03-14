import streamlit as st
from datetime import datetime
from utils.auth import is_logged_in, require_login_for_action
from utils.bigquery_client import query, insert_rows


st.subheader("⚙️ 管理者画面")

# 管理者チェック（ログイン済みの場合のみ）
if is_logged_in() and not st.session_state.get('is_admin', False):
    st.error("⛔ この画面は管理者のみ操作できます")

if not is_logged_in():
    st.info("💡 操作にはログインが必要です（管理者のみ）")

# --- 承認待ちリクエスト ---
st.subheader("📬 承認待ちリクエスト")

pending = query("""
    SELECT
        r.request_id,
        r.user_id,
        u.user_name,
        r.exercise_name,
        r.body_part_id,
        r.reason,
        r.created_at
    FROM raw.exercise_request r
    LEFT JOIN mart.d_user u ON r.user_id = u.user_id
    WHERE r.status = 'pending'
    ORDER BY r.created_at
""")

if not pending.empty:
    for _, row in pending.iterrows():
        with st.expander(
            f"📝 {row['exercise_name']}（{row['body_part_id']}）"
            f"- {row['user_name']} - {row['created_at'].strftime('%Y/%m/%d')}"
        ):
            st.markdown(f"**種目名:** {row['exercise_name']}")
            st.markdown(f"**部位:** {row['body_part_id']}")
            st.markdown(f"**リクエスト者:** {row['user_name']}")
            if row['reason']:
                st.markdown(f"**理由:** {row['reason']}")

            col_approve, col_reject = st.columns(2)

            with col_approve:
                if st.button("✅ 承認", key=f"approve_{row['request_id']}"):
                    st.session_state[f"approving_{row['request_id']}"] = True

            with col_reject:
                if st.button("❌ 却下", key=f"reject_{row['request_id']}"):
                    # 却下処理
                    query(f"""
                        UPDATE raw.exercise_request
                        SET status = 'rejected',
                            reviewed_by = '{st.session_state.user_id}',
                            reviewed_at = CURRENT_TIMESTAMP()
                        WHERE request_id = '{row['request_id']}'
                    """)
                    st.success("却下しました")
                    st.rerun()

            # 承認時の追加設定フォーム
            if st.session_state.get(f"approving_{row['request_id']}", False):
                st.markdown("---")
                st.markdown("**承認時の追加設定**")

                exercise_id = st.text_input(
                    "種目ID（英数字・アンダースコア）",
                    value=row['exercise_name'].lower().replace(' ', '_'),
                    key=f"eid_{row['request_id']}"
                )
                is_compound = st.checkbox(
                    "複合種目（KPI対象）",
                    key=f"compound_{row['request_id']}"
                )
                display_order = st.number_input(
                    "表示順",
                    min_value=1, max_value=100, value=10,
                    key=f"order_{row['request_id']}"
                )

                if st.button("💾 承認して追加", key=f"confirm_{row['request_id']}"):
                    # 種目マスタに追加
                    new_exercise = {
                        'exercise_id': exercise_id,
                        'exercise_name': row['exercise_name'],
                        'body_part_id': row['body_part_id'],
                        'is_compound': is_compound,
                        'is_active': True,
                        'display_order': display_order,
                        'updated_at': datetime.utcnow().isoformat()
                    }
                    try:
                        insert_rows(
                            'training-assistant-prod.raw.exercise_master',
                            [new_exercise]
                        )
                        # リクエストステータス更新
                        query(f"""
                            UPDATE raw.exercise_request
                            SET status = 'approved',
                                reviewed_by = '{st.session_state.user_id}',
                                reviewed_at = CURRENT_TIMESTAMP()
                            WHERE request_id = '{row['request_id']}'
                        """)
                        st.success(f"「{row['exercise_name']}」を承認・追加しました")
                        st.session_state.pop(f"approving_{row['request_id']}", None)
                        st.rerun()
                    except Exception as e:
                        st.error(f"エラー: {e}")
else:
    st.info("承認待ちのリクエストはありません")

# --- 種目マスタ管理 ---
st.markdown("---")
st.subheader("📋 種目マスタ管理")

body_parts = query("SELECT body_part_id, body_part_name FROM mart.d_body_part ORDER BY sort_order")
bp_filter = st.selectbox(
    "部位フィルタ",
    options=["全部位"] + body_parts['body_part_id'].tolist(),
    format_func=lambda x: "全部位" if x == "全部位" else body_parts[body_parts['body_part_id']==x]['body_part_name'].values[0]
)

bp_where = ""
if bp_filter != "全部位":
    bp_where = f"WHERE body_part_id = '{bp_filter}'"

exercises = query(f"""
    SELECT exercise_id, exercise_name, body_part_id, is_compound, is_active, display_order
    FROM raw.exercise_master
    {bp_where}
    ORDER BY body_part_id, display_order
""")

if not exercises.empty:
    st.dataframe(exercises, hide_index=True, use_container_width=True)

    # 無効化
    st.markdown("**種目の無効化**")
    ex_to_disable = st.selectbox(
        "無効化する種目",
        options=exercises[exercises['is_active']==True]['exercise_id'].tolist(),
        format_func=lambda x: exercises[exercises['exercise_id']==x]['exercise_name'].values[0]
    )
    if st.button("🚫 無効化"):
        require_login_for_action()
        query(f"""
            UPDATE raw.exercise_master
            SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP()
            WHERE exercise_id = '{ex_to_disable}'
        """)
        st.success(f"「{ex_to_disable}」を無効化しました")
        st.rerun()

# --- 種目の手動追加 ---
st.markdown("---")
st.subheader("➕ 種目の手動追加")

new_id = st.text_input("種目ID（英数字・アンダースコア）")
new_name = st.text_input("種目名")
new_bp = st.selectbox(
    "部位",
    options=body_parts['body_part_id'].tolist(),
    format_func=lambda x: body_parts[body_parts['body_part_id']==x]['body_part_name'].values[0],
    key="manual_bp"
)
new_compound = st.checkbox("複合種目（KPI対象）")
new_order = st.number_input("表示順", min_value=1, max_value=100, value=10)

if st.button("💾 追加"):
    require_login_for_action()
    if not new_id or not new_name:
        st.error("種目IDと種目名は必須です")
    elif not new_id.replace('_', '').isalnum():
        st.error("種目IDは英数字とアンダースコアのみ使用可能です")
    else:
        existing = query(f"""
            SELECT COUNT(*) AS cnt FROM raw.exercise_master
            WHERE exercise_id = '{new_id}'
        """)
        if existing['cnt'].iloc[0] > 0:
            st.error("既に使用されているIDです")
        else:
            row = {
                'exercise_id': new_id,
                'exercise_name': new_name,
                'body_part_id': new_bp,
                'is_compound': new_compound,
                'is_active': True,
                'display_order': new_order,
                'updated_at': datetime.utcnow().isoformat()
            }
            try:
                insert_rows('training-assistant-prod.raw.exercise_master', [row])
                st.success(f"「{new_name}」を追加しました")
                st.rerun()
            except Exception as e:
                st.error(f"エラー: {e}")