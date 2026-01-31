"""YESOD Admin Dashboard."""
import streamlit as st
import pandas as pd
from config import settings
import db
import valkey_client

st.set_page_config(
    page_title="YESOD Admin",
    page_icon="🔐",
    layout="wide",
)


def check_auth():
    """Simple authentication check."""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    
    if not st.session_state.authenticated:
        st.title("🔐 YESOD Admin Login")
        
        with st.form("login"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login")
            
            if submitted:
                if username == settings.ADMIN_USER and password == settings.ADMIN_PASSWORD:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Invalid credentials")
        return False
    return True


def main():
    if not check_auth():
        return
    
    st.title("🔐 YESOD Admin Dashboard")
    
    # Sidebar navigation
    page = st.sidebar.radio(
        "Navigation",
        ["📊 Overview", "👥 Users", "🔑 Sessions", "⚡ Valkey Status"]
    )
    
    if st.sidebar.button("🔄 Refresh"):
        st.rerun()
    
    if st.sidebar.button("🚪 Logout"):
        st.session_state.authenticated = False
        st.rerun()
    
    if page == "📊 Overview":
        show_overview()
    elif page == "👥 Users":
        show_users()
    elif page == "🔑 Sessions":
        show_sessions()
    elif page == "⚡ Valkey Status":
        show_valkey_status()


def show_overview():
    st.header("Overview")
    
    try:
        stats = db.get_stats()
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Users", stats["total_users"])
        col2.metric("OAuth Accounts", stats["total_oauth_accounts"])
        col3.metric("Active Sessions", stats["active_sessions"])
        
    except Exception as e:
        st.error(f"Failed to load stats: {e}")


def show_users():
    st.header("Users")
    
    try:
        users_df = db.get_users()
        
        if users_df.empty:
            st.info("No users found")
            return
        
        st.dataframe(
            users_df,
            use_container_width=True,
            hide_index=True,
        )
        
        # User details
        st.subheader("User Details")
        user_ids = users_df["ID"].astype(str).tolist()
        selected_user = st.selectbox("Select User", user_ids)
        
        if selected_user:
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**OAuth Accounts**")
                oauth_df = db.get_user_oauth_accounts(selected_user)
                if not oauth_df.empty:
                    st.dataframe(oauth_df, hide_index=True)
                else:
                    st.info("No OAuth accounts")
            
            with col2:
                st.write("**Actions**")
                if st.button("🚫 Revoke All Sessions", key="revoke_all"):
                    count = db.revoke_all_user_sessions(selected_user)
                    st.success(f"Revoked {count} sessions")
                    st.rerun()
                    
    except Exception as e:
        st.error(f"Failed to load users: {e}")


def show_sessions():
    st.header("Sessions (Refresh Tokens)")
    
    try:
        sessions_df = db.get_sessions()
        
        if sessions_df.empty:
            st.info("No sessions found")
            return
        
        # Filter options
        col1, col2 = st.columns(2)
        with col1:
            show_revoked = st.checkbox("Show revoked", value=False)
        with col2:
            show_expired = st.checkbox("Show expired", value=False)
        
        filtered_df = sessions_df.copy()
        if not show_revoked:
            filtered_df = filtered_df[filtered_df["Revoked"] == False]
        if not show_expired:
            filtered_df = filtered_df[
                pd.to_datetime(filtered_df["Expires At"]) > pd.Timestamp.now(tz="UTC")
            ]
        
        st.dataframe(
            filtered_df,
            use_container_width=True,
            hide_index=True,
        )
        
        # Revoke specific session
        st.subheader("Revoke Session")
        session_ids = filtered_df["ID"].astype(str).tolist()
        if session_ids:
            selected_session = st.selectbox("Select Session to Revoke", session_ids)
            if st.button("🚫 Revoke Selected Session"):
                db.revoke_session(selected_session)
                st.success("Session revoked")
                st.rerun()
        
    except Exception as e:
        st.error(f"Failed to load sessions: {e}")


def show_valkey_status():
    st.header("Valkey Status")
    
    try:
        # OAuth States
        st.subheader("Active OAuth States")
        states = valkey_client.get_oauth_states()
        if states:
            st.dataframe(pd.DataFrame(states), hide_index=True)
        else:
            st.info("No active OAuth states")
        
        # Rate Limits
        st.subheader("Rate Limit Entries")
        limits = valkey_client.get_rate_limit_info()
        if limits:
            st.dataframe(pd.DataFrame(limits), hide_index=True)
        else:
            st.info("No rate limit entries")
            
    except Exception as e:
        st.error(f"Failed to connect to Valkey: {e}")


if __name__ == "__main__":
    main()
