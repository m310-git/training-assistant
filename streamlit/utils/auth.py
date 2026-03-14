import streamlit as st
import hashlib
from datetime import datetime, timedelta

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def is_logged_in():
    """ログイン済みかつ1時間以内かを返す"""
    if not st.session_state.get("authenticated", False):
        return False
    
    login_time = st.session_state.get("login_time")
    if login_time and datetime.now() - login_time > timedelta(hours=1):
        # 1時間超過 → セッションクリア
        st.session_state.clear()
        return False
    
    return True

def check_password():
    """ログインフォーム表示"""
    if is_logged_in():
        return True

    st.title("🔐 ログイン")

    user_id = st.text_input("ユーザーID")
    password = st.text_input("パスワード", type="password")

    if st.button("ログイン"):
        if user_id in st.secrets["passwords"]:
            if hash_password(password) == st.secrets["passwords"][user_id]:
                st.session_state.authenticated = True
                st.session_state.user_id = user_id
                st.session_state.user_name = st.secrets["users"][user_id]["name"]
                st.session_state.is_admin = st.secrets["users"][user_id]["is_admin"]
                st.session_state.login_time = datetime.now()
                st.rerun()
            else:
                st.error("パスワードが正しくありません")
        else:
            st.error("ユーザーIDが見つかりません")

    return False

def require_login_for_action():
    """データ変更時にログインを要求"""
    if not is_logged_in():
        st.session_state.login_redirect = True
        st.warning("⚠️ この操作にはログインが必要です")
        st.switch_page("app.py")
        st.stop()

def get_user_id_or_default():
    """ログイン済みならuser_id、未ログインならデフォルト"""
    if is_logged_in():
        return st.session_state.user_id
    return 'user_001'