import streamlit as st
import hashlib

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def is_logged_in():
    if st.session_state.get("authenticated", False):
        # ログイン済みなら毎回URLにuidを維持
        if "uid" not in st.query_params:
            st.query_params["uid"] = st.session_state.user_id
        return True

    # URLパラメータから復元
    params = st.query_params
    user_id = params.get("uid")

    if user_id and user_id in st.secrets["passwords"]:
        st.session_state.authenticated = True
        st.session_state.user_id = user_id
        st.session_state.user_name = st.secrets["users"][user_id]["name"]
        st.session_state.is_admin = st.secrets["users"][user_id]["is_admin"]
        # URLパラメータを再セット（ページ遷移で消えないように）
        st.query_params["uid"] = user_id
        return True

    return False

def check_password():
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
                st.query_params["uid"] = user_id
                st.rerun()
            else:
                st.error("パスワードが正しくありません")
        else:
            st.error("ユーザーIDが見つかりません")
    return False

def logout():
    st.query_params.clear()
    st.session_state.clear()

def require_login_for_action():
    if not is_logged_in():
        st.warning("⚠️ この操作にはログインが必要です")
        st.switch_page("app.py")
        st.stop()