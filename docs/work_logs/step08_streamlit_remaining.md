# Step 8: Streamlit残り画面

## 概要

ランキング・ソーシャル・種目追加リクエスト・管理者画面を構築する。

## 前提条件

- [ ] Step 6 完了
- [ ] mart層のランキング・個人記録テーブルにデータが存在する

---

## 手順

### 8-1. ランキングページ

#### streamlit/pages/4_🏆_Ranking.py

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

### 8-2. ソーシャルページ

#### streamlit/pages/5_👥_Social.py

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

### 8-3. 種目追加リクエストページ

#### streamlit/pages/6_➕_ExerciseRequest.py

    import streamlit as st
    import uuid
    from datetime import datetime
    from utils.auth import check_password
    from utils.bigquery_client import query, insert_rows

    if not check_password():
        st.stop()

    st.title("➕ 種目追加リクエスト")

    user_id = st.session_state.user_id

    # --- 新規リクエスト ---
    st.subheader("新規リクエスト")

    body_parts = query("SELECT body_part_id, body_part_name FROM mart.d_body_part ORDER BY sort_order")

    exercise_name = st.text_input("種目名", max_chars=30)
    selected_bp = st.selectbox(
        "部位",
        options=body_parts['body_part_id'].tolist(),
        format_func=lambda x: body_parts[body_parts['body_part_id']==x]['body_part_name'].values[0]
    )
    reason = st.text_area("追加理由（任意）", max_chars=500)

    if st.button("📤 リクエスト送信"):
        if not exercise_name or len(exercise_name) < 2:
            st.error("種目名を2文字以上で入力してください")
        else:
            # 既存種目との重複チェック
            existing = query(f"""
                SELECT COUNT(*) AS cnt
                FROM raw.exercise_master
                WHERE LOWER(exercise_name) = LOWER('{exercise_name}')
            """)
            if existing['cnt'].iloc[0] > 0:
                st.error("既に登録されている種目です")
            else:
                # 承認待ちリクエストとの重複チェック
                pending = query(f"""
                    SELECT COUNT(*) AS cnt
                    FROM raw.exercise_request
                    WHERE LOWER(exercise_name) = LOWER('{exercise_name}')
                      AND status = 'pending'
                """)
                if pending['cnt'].iloc[0] > 0:
                    st.warning("同じ種目名のリクエストが既に承認待ちです")
                else:
                    row = {
                        'request_id': str(uuid.uuid4()),
                        'user_id': user_id,
                        'exercise_name': exercise_name,
                        'body_part_id': selected_bp,
                        'reason': reason if reason else None,
                        'status': 'pending',
                        'reviewed_by': None,
                        'created_at': datetime.utcnow().isoformat(),
                        'reviewed_at': None
                    }
                    try:
                        insert_rows('training-assistant-prod.raw.exercise_request', [row])
                        st.success("リクエストを送信しました！管理者の承認をお待ちください。")
                    except Exception as e:
                        st.error(f"送信エラー: {e}")

    # --- リクエスト履歴 ---
    st.markdown("---")
    st.subheader("📋 リクエスト履歴")

    history = query(f"""
        SELECT
            created_at,
            exercise_name,
            body_part_id,
            status,
            reviewed_at
        FROM raw.exercise_request
        WHERE user_id = '{user_id}'
        ORDER BY created_at DESC
    """)

    if not history.empty:
        status_icons = {"pending": "⏳ 承認待ち", "approved": "✅ 承認済み", "rejected": "❌ 却下"}
        for _, row in history.iterrows():
            icon = status_icons.get(row['status'], row['status'])
            st.markdown(
                f"**{row['created_at'].strftime('%Y/%m/%d')}** "
                f"{row['exercise_name']}（{row['body_part_id']}）　{icon}"
            )
    else:
        st.info("リクエスト履歴はありません")

### 8-4. 管理者画面

#### streamlit/pages/7_⚙️_Admin.py

    import streamlit as st
    import uuid
    from datetime import datetime
    from utils.auth import check_password
    from utils.bigquery_client import query, insert_rows

    if not check_password():
        st.stop()

    # 管理者チェック
    if not st.session_state.get('is_admin', False):
        st.error("⛔ この画面は管理者のみアクセスできます")
        st.stop()

    st.title("⚙️ 管理者画面")

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

### 8-5. ローカル動作確認

    cd streamlit
    streamlit run app.py

確認項目:
- ランキング画面: 週間/月間/全期間タブが切り替わる
- ランキング画面: 部位別ランキングが表示される
- ソーシャル画面: 記録更新フィードが表示される
- ソーシャル画面: 他ユーザーの記録が閲覧できる
- 種目リクエスト画面: リクエスト送信ができる
- 種目リクエスト画面: 履歴が表示される
- 管理者画面: is_admin=TRUE のユーザーのみアクセスできる
- 管理者画面: 承認/却下が動作する
- 管理者画面: 種目マスタの管理ができる

### 8-6. Gitコミット＆プッシュ

    git add streamlit/pages/ docs/work_logs/
    git commit -m "feat: ranking, social, exercise request, and admin pages"
    git push origin main

---

## 現在のStreamlit構成

    streamlit/
    ├── app.py
    ├── .streamlit/
    │   ├── config.toml
    │   └── secrets.toml        ← Git管理外
    ├── pages/
    │   ├── 1_📝_Input.py
    │   ├── 2_📅_Calendar.py
    │   ├── 3_📊_Dashboard.py
    │   ├── 4_🏆_Ranking.py
    │   ├── 5_👥_Social.py
    │   ├── 6_➕_ExerciseRequest.py
    │   └── 7_⚙️_Admin.py
    └── utils/
        ├── auth.py
        ├── bigquery_client.py
        └── validators.py

---

## 完了チェックリスト

- [ ] ランキング画面（週間/月間/全期間/部位別）が動作する
- [ ] ソーシャル画面（記録更新フィード・他ユーザー閲覧）が動作する
- [ ] 種目追加リクエスト画面（送信・履歴）が動作する
- [ ] 管理者画面（承認/却下・マスタ管理・手動追加）が動作する
- [ ] 管理者画面のアクセス制御が動作する（is_admin=FALSEはアクセス不可）
- [ ] 一般ユーザーのサイドバーに管理者画面が表示されない
- [ ] Gitにpush済み
