# Step 6: Streamlitダッシュボード・カレンダー

## 概要

ダッシュボード（KPIカード・進捗グラフ）とカレンダー画面を構築する。

## 前提条件

- [ ] Step 5 完了
- [ ] mart.m_progress_curve にデータが存在する
- [ ] mart.m_calendar にデータが存在する

---

## 手順

### 6-1. ダッシュボードページ

#### streamlit/pages/3_📊_Dashboard.py

    import streamlit as st
    import plotly.express as px
    from utils.auth import check_password
    from utils.bigquery_client import query

    if not check_password():
        st.stop()

    st.title("📊 ダッシュボード")

    # ユーザー切り替え
    users = query("SELECT user_id, user_name FROM mart.d_user")
    selected_user = st.selectbox(
        "ユーザー",
        options=users['user_id'].tolist(),
        format_func=lambda x: users[users['user_id']==x]['user_name'].values[0],
        index=users['user_id'].tolist().index(st.session_state.user_id)
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

### 6-2. カレンダーページ

#### streamlit/pages/2_📅_Calendar.py

    import streamlit as st
    from datetime import datetime, date
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

    # カレンダーデータ取得
    year = st.session_state.cal_year
    month = st.session_state.cal_month
    first_day = date(year, month, 1)
    last_day = date(year, month, calendar.monthrange(year, month)[1])

    cal_data = query(f"""
        SELECT training_date, body_parts, total_volume, exercise_count, exercise_summary
        FROM mart.m_calendar
        WHERE user_id = '{selected_user}'
          AND training_date BETWEEN '{first_day}' AND '{last_day}'
        ORDER BY training_date
    """)

    # カレンダー表示
    cal_dict = {}
    if not cal_data.empty:
        for _, row in cal_data.iterrows():
            cal_dict[row['training_date']] = row

    # 曜日ヘッダー
    st.markdown("| 月 | 火 | 水 | 木 | 金 | 土 | 日 |")
    st.markdown("|---|---|---|---|---|---|---|")

    cal = calendar.Calendar(firstweekday=0)
    weeks = cal.monthdayscalendar(year, month)

    for week in weeks:
        row_cells = []
        for day_num in week:
            if day_num == 0:
                row_cells.append(" ")
            else:
                d = date(year, month, day_num)
                if d in cal_dict:
                    bp = cal_dict[d]['body_parts']
                    row_cells.append(f"**{day_num}** 🟢{bp}")
                else:
                    row_cells.append(str(day_num))
        st.markdown("| " + " | ".join(row_cells) + " |")

    # 日付クリックで詳細表示
    st.subheader("📋 日付の詳細")
    selected_date = st.date_input(
        "日付を選択",
        value=today,
        min_value=first_day,
        max_value=last_day
    )

    if selected_date in cal_dict:
        info = cal_dict[selected_date]
        st.markdown(f"**部位:** {info['body_parts']}")
        st.markdown(f"**総ボリューム:** {info['total_volume']:,.1f} kg")
        st.markdown(f"**種目数:** {info['exercise_count']}")

        # 詳細データ取得
        detail = query(f"""
            SELECT exercise_name, set_number, weight_kg, reps, rpe, volume
            FROM mart.fct_training_set
            WHERE user_id = '{selected_user}'
              AND training_date = '{selected_date}'
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

        # 編集ボタン（自分の記録 & 3時間以内のみ）
        if selected_user == st.session_state.user_id:
            created_check = query(f"""
                SELECT MIN(created_at) AS earliest
                FROM raw.training_log
                WHERE user_id = '{selected_user}'
                  AND training_date = '{selected_date}'
                  AND is_deleted = FALSE
            """)
            if not created_check.empty and created_check['earliest'].values[0]:
                from datetime import datetime, timedelta
                import pandas as pd
                earliest = pd.Timestamp(created_check['earliest'].values[0])
                if datetime.utcnow() < earliest + timedelta(hours=3):
                    if st.button("✏️ 編集する"):
                        st.session_state.edit_date = selected_date
                        st.switch_page("pages/1_📝_Input.py")
    else:
        st.info("この日のトレーニング記録はありません")

### 6-3. ローカル動作確認

    cd streamlit
    streamlit run app.py

確認項目:
- ダッシュボード画面が表示される
- KPIカードに複合種目の週次変化率が表示される
- 進捗グラフが描画される
- 種目別グラフが切り替わる
- カレンダーにトレーニング日がマーク表示される
- 日付選択で詳細が表示される
- 編集ボタンが3時間以内のみ表示される

### 6-4. Gitコミット＆プッシュ

    git add streamlit/pages/ docs/work_logs/
    git commit -m "feat: dashboard and calendar pages"
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
    │   └── 3_📊_Dashboard.py
    └── utils/
        ├── auth.py
        ├── bigquery_client.py
        └── validators.py

---

## 完了チェックリスト

- [ ] ダッシュボード画面が表示される
- [ ] KPIカード（4種目）が表示される
- [ ] 7日間移動平均グラフが描画される
- [ ] 種目別グラフが動作する
- [ ] 期間フィルタが動作する
- [ ] ユーザー切り替えが動作する
- [ ] カレンダーにトレーニング日がマーク表示される
- [ ] 月切り替えが動作する
- [ ] 日付詳細が表示される
- [ ] 編集ボタンが条件付きで表示される
- [ ] Gitにpush済み

