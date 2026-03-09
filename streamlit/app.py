import streamlit as st
from utils.auth import check_password

st.set_page_config(
    page_title="トレーニングアシスタント",
    page_icon="🏋️",
    layout="wide"
)

if not check_password():
    st.stop()

st.title("🏋️ トレーニングアシスタント")
st.write(f"ようこそ、{st.session_state.user_name}さん！")

st.markdown("""
### メニュー
- 📝 **Input** - トレーニング記録の入力
- 📅 **Calendar** - カレンダー表示
- 📊 **Dashboard** - 進捗ダッシュボード
- 🏆 **Ranking** - ランキング
- 👥 **Social** - 他ユーザーの記録
""")

if st.button("ログアウト"):
    st.session_state.clear()
    st.rerun()