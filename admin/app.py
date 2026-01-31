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


def show_api_test():
    st.header("🧪 API Test Console")
    
    API_BASE = "http://localhost:8000/api/v1"  # Use localhost for browser access
    
    # Token management
    st.subheader("1. Get Authentication Token")
    
    st.markdown("""
    **Step 1:** Click a login link below to authenticate via OAuth
    
    **Step 2:** After login, you'll see a page with your tokens
    
    **Step 3:** Copy the tokens and paste them below
    """)
    
    st.markdown(f"""
    <div style="display: flex; gap: 20px; margin: 20px 0;">
        <a href="{API_BASE}/auth/google" target="_blank" 
           style="background: #4285f4; color: white; padding: 12px 24px; 
                  border-radius: 8px; text-decoration: none; font-weight: bold;">
            🔵 Login with Google
        </a>
        <a href="{API_BASE}/auth/discord" target="_blank"
           style="background: #5865f2; color: white; padding: 12px 24px;
                  border-radius: 8px; text-decoration: none; font-weight: bold;">
            🟣 Login with Discord
        </a>
    </div>
    """, unsafe_allow_html=True)
    
    st.info(f"💡 If buttons don't work, open these URLs directly:\n\n"
            f"Google: {API_BASE}/auth/google\n\n"
            f"Discord: {API_BASE}/auth/discord")
    
    st.divider()
    
    st.subheader("2. Enter Tokens")
    
    if "test_access_token" not in st.session_state:
        st.session_state.test_access_token = ""
    if "test_refresh_token" not in st.session_state:
        st.session_state.test_refresh_token = ""
    
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.test_access_token = st.text_input(
            "Access Token",
            value=st.session_state.test_access_token,
            type="password",
        )
    with col2:
        st.session_state.test_refresh_token = st.text_input(
            "Refresh Token",
            value=st.session_state.test_refresh_token,
            type="password",
        )
    
    st.divider()
    
    st.subheader("3. Test APIs")
    
    # Test sections (Delete Account removed for safety)
    tab1, tab2, tab3 = st.tabs([
        "👤 User Profile", "🔗 Account Link", "📱 Sessions"
    ])
    
    headers = {"Authorization": f"Bearer {st.session_state.test_access_token}"}
    
    # Use internal Docker network for API calls
    API_INTERNAL = "http://api:8000/api/v1"
    
    with tab1:
        st.subheader("User Profile Management")
        
        if st.button("GET /users/me", key="get_user"):
            try:
                import requests
                resp = requests.get(f"{API_INTERNAL}/users/me", headers=headers)
                st.json(resp.json())
                st.write(f"Status: {resp.status_code}")
            except Exception as e:
                st.error(f"Error: {e}")
        
        st.divider()
        
        st.write("**Update Profile**")
        new_display_name = st.text_input("New Display Name", key="new_name")
        new_avatar_url = st.text_input("New Avatar URL", key="new_avatar")
        
        if st.button("PATCH /users/me", key="update_user"):
            try:
                import requests
                data = {}
                if new_display_name:
                    data["display_name"] = new_display_name
                if new_avatar_url:
                    data["avatar_url"] = new_avatar_url
                
                resp = requests.patch(
                    f"{API_INTERNAL}/users/me",
                    headers=headers,
                    json=data,
                )
                st.json(resp.json())
                st.write(f"Status: {resp.status_code}")
            except Exception as e:
                st.error(f"Error: {e}")
    
    with tab2:
        st.subheader("OAuth Account Linking")
        
        if st.button("GET /accounts", key="list_accounts"):
            try:
                import requests
                resp = requests.get(f"{API_INTERNAL}/accounts", headers=headers)
                st.json(resp.json())
                st.write(f"Status: {resp.status_code}")
            except Exception as e:
                st.error(f"Error: {e}")
        
        st.divider()
        
        st.write("**Link New Provider**")
        link_provider = st.selectbox("Provider to Link", ["google", "discord"], key="link_prov")
        st.write(f"Link URL: `{API_BASE}/accounts/link/{link_provider}`")
        st.warning("⚠️ This requires browser redirect. Open the URL manually with valid token.")
        
        st.divider()
        
        st.write("**Unlink Provider**")
        unlink_provider = st.selectbox("Provider to Unlink", ["google", "discord"], key="unlink_prov")
        
        if st.button(f"DELETE /accounts/{unlink_provider}", key="unlink"):
            try:
                import requests
                resp = requests.delete(
                    f"{API_INTERNAL}/accounts/{unlink_provider}",
                    headers=headers,
                )
                st.json(resp.json())
                st.write(f"Status: {resp.status_code}")
            except Exception as e:
                st.error(f"Error: {e}")
    
    with tab3:
        st.subheader("Session Management")
        
        if st.button("GET /sessions", key="list_sessions"):
            try:
                import requests
                resp = requests.get(f"{API_INTERNAL}/sessions", headers=headers)
                data = resp.json()
                st.json(data)
                st.write(f"Status: {resp.status_code}")
                
                if "sessions" in data:
                    st.session_state.session_ids = [s["id"] for s in data["sessions"]]
            except Exception as e:
                st.error(f"Error: {e}")
        
        st.divider()
        
        st.write("**Revoke Specific Session**")
        session_id = st.text_input("Session ID to Revoke", key="revoke_session_id")
        
        if st.button("DELETE /sessions/{id}", key="revoke_one"):
            if session_id:
                try:
                    import requests
                    resp = requests.delete(
                        f"{API_INTERNAL}/sessions/{session_id}",
                        headers=headers,
                    )
                    st.json(resp.json())
                    st.write(f"Status: {resp.status_code}")
                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.warning("Enter a session ID")
        
        st.divider()
        
        if st.button("DELETE /sessions (Revoke All)", key="revoke_all_sessions"):
            try:
                import requests
                resp = requests.delete(f"{API_INTERNAL}/sessions", headers=headers)
                st.json(resp.json())
                st.write(f"Status: {resp.status_code}")
            except Exception as e:
                st.error(f"Error: {e}")


def main():
    if not check_auth():
        return
    
    st.title("🔐 YESOD Admin Dashboard")
    
    # Sidebar navigation
    page = st.sidebar.radio(
        "Navigation",
        ["📊 Overview", "👥 Users", "🔑 Sessions", "⚡ Valkey Status", "🧪 API Test"]
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
    elif page == "🧪 API Test":
        show_api_test()


if __name__ == "__main__":
    main()
