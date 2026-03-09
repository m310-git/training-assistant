import streamlit as st
import hashlib

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def check_password():
    if "authenticated" in st.session_state and st.session_state.authenticated:
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
                st.rerun()
            else:
                st.error("パスワードが正しくありません")
        else:
            st.error("ユーザーIDが見つかりません")

    return False