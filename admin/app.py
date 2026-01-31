"""YESOD Admin Dashboard."""
import streamlit as st
import pandas as pd
import graphviz
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


def show_audit_logs():
    st.header("📋 Audit Logs")
    
    try:
        # Stats
        stats = db.get_audit_stats()
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Logins (24h) ✅", stats["logins_success_24h"])
        col2.metric("Logins (24h) ❌", stats["logins_failed_24h"])
        col3.metric("Events (24h)", stats["events_24h"])
        
        st.divider()
        
        # Tabs for different log types
        tab1, tab2 = st.tabs(["🔐 Login History", "📝 Auth Events"])
        
        with tab1:
            st.subheader("Login History")
            
            login_df = db.get_login_history(100)
            if login_df.empty:
                st.info("No login history found. Audit schema may not be initialized yet.")
            else:
                # Filter options
                col1, col2 = st.columns(2)
                with col1:
                    show_success = st.checkbox("Show successful", value=True, key="login_success")
                with col2:
                    show_failed = st.checkbox("Show failed", value=True, key="login_failed")
                
                filtered_df = login_df.copy()
                if not show_success:
                    filtered_df = filtered_df[filtered_df["Success"] == False]
                if not show_failed:
                    filtered_df = filtered_df[filtered_df["Success"] == True]
                
                st.dataframe(filtered_df, use_container_width=True, hide_index=True)
        
        with tab2:
            st.subheader("Authentication Events")
            
            events_df = db.get_auth_events(100)
            if events_df.empty:
                st.info("No auth events found. Audit schema may not be initialized yet.")
            else:
                # Filter by event type
                event_types = events_df["Event Type"].unique().tolist()
                selected_types = st.multiselect(
                    "Filter by Event Type",
                    event_types,
                    default=event_types,
                )
                
                filtered_df = events_df[events_df["Event Type"].isin(selected_types)]
                st.dataframe(filtered_df, use_container_width=True, hide_index=True)
    
    except Exception as e:
        st.error(f"Failed to load audit logs: {e}")


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
        
        st.divider()
        
        st.write("**Sync from OAuth Provider**")
        st.caption("Restore display name and avatar from your linked OAuth account")
        sync_provider = st.selectbox("Provider", ["google", "discord"], key="sync_prov")
        
        if st.button(f"POST /users/me/sync-from-provider?provider={sync_provider}", key="sync_profile"):
            try:
                import requests
                resp = requests.post(
                    f"{API_INTERNAL}/users/me/sync-from-provider?provider={sync_provider}",
                    headers=headers,
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
        st.caption("Add another OAuth provider to your account")
        
        st.markdown(f"""
        <div style="display: flex; gap: 20px; margin: 20px 0;">
            <a href="{API_BASE}/accounts/link/google" target="_blank" 
               style="background: #4285f4; color: white; padding: 12px 24px; 
                      border-radius: 8px; text-decoration: none; font-weight: bold;">
                🔵 Link Google
            </a>
            <a href="{API_BASE}/accounts/link/discord" target="_blank"
               style="background: #5865f2; color: white; padding: 12px 24px;
                      border-radius: 8px; text-decoration: none; font-weight: bold;">
                🟣 Link Discord
            </a>
        </div>
        """, unsafe_allow_html=True)
        
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


def show_db_schema():
    st.header("🗄️ Database Schema")
    
    try:
        table_info = db.get_table_info()
        relationships = db.get_table_relationships()
        
        # Tab layout
        tab1, tab2, tab3 = st.tabs(["📊 ER Diagram", "📋 Tables", "📈 Statistics"])
        
        with tab1:
            st.subheader("Entity Relationship Diagram")
            
            # Create ER diagram using Graphviz
            dot = graphviz.Digraph(comment="YESOD ER Diagram")
            dot.attr(rankdir="LR", splines="ortho")
            dot.attr("node", shape="record", fontname="Helvetica", fontsize="10")
            dot.attr("edge", fontname="Helvetica", fontsize="9")
            
            # Add tables as nodes
            for table_name, info in table_info.items():
                # Build label with columns
                pk_cols = set(info["primary_keys"])
                fk_cols = {fk["column"] for fk in info["foreign_keys"]}
                
                cols_str = ""
                for col in info["columns"]:
                    prefix = ""
                    if col["name"] in pk_cols:
                        prefix = "🔑 "
                    elif col["name"] in fk_cols:
                        prefix = "🔗 "
                    cols_str += f"{prefix}{col['name']}: {col['type']}\\l"
                
                label = f"{{{table_name}|{cols_str}}}"
                
                # Color based on table type
                if table_name == "users":
                    dot.node(table_name, label, fillcolor="#e3f2fd", style="filled")
                elif table_name.startswith("user_"):
                    dot.node(table_name, label, fillcolor="#f3e5f5", style="filled")
                elif table_name == "deleted_users":
                    dot.node(table_name, label, fillcolor="#ffebee", style="filled")
                elif table_name == "alembic_version":
                    dot.node(table_name, label, fillcolor="#f5f5f5", style="filled")
                else:
                    dot.node(table_name, label, fillcolor="#e8f5e9", style="filled")
            
            # Add relationships as edges
            for rel in relationships:
                dot.edge(
                    rel["from_table"], 
                    rel["to_table"],
                    label=f"{rel['from_column']}",
                    arrowhead="crow",
                )
            
            st.graphviz_chart(dot)
            
            # Legend
            st.markdown("""
            **Legend:**
            - 🔑 Primary Key
            - 🔗 Foreign Key
            - 🔵 Core (users)
            - 🟣 User-related tables
            - 🔴 Deleted users
            - 🟢 Other tables
            """)
        
        with tab2:
            st.subheader("Table Details")
            
            # Table selector
            selected_table = st.selectbox(
                "Select Table",
                list(table_info.keys()),
            )
            
            if selected_table:
                info = table_info[selected_table]
                
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.write("**Columns**")
                    cols_df = pd.DataFrame(info["columns"])
                    cols_df["PK"] = cols_df["name"].isin(info["primary_keys"])
                    fk_cols = {fk["column"] for fk in info["foreign_keys"]}
                    cols_df["FK"] = cols_df["name"].isin(fk_cols)
                    st.dataframe(cols_df, hide_index=True, use_container_width=True)
                
                with col2:
                    st.write("**Info**")
                    st.metric("Row Count", info["row_count"])
                    
                    if info["foreign_keys"]:
                        st.write("**Foreign Keys**")
                        for fk in info["foreign_keys"]:
                            st.write(f"- `{fk['column']}` → `{fk['references_table']}.{fk['references_column']}`")
        
        with tab3:
            st.subheader("Database Statistics")
            
            # Summary metrics
            total_tables = len(table_info)
            total_rows = sum(info["row_count"] for info in table_info.values())
            total_relationships = len(relationships)
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Tables", total_tables)
            col2.metric("Total Rows", total_rows)
            col3.metric("Relationships", total_relationships)
            
            st.divider()
            
            # Row counts per table
            st.write("**Rows per Table**")
            stats_data = [
                {"Table": name, "Rows": info["row_count"], "Columns": len(info["columns"])}
                for name, info in table_info.items()
            ]
            stats_df = pd.DataFrame(stats_data).sort_values("Rows", ascending=False)
            st.dataframe(stats_df, hide_index=True, use_container_width=True)
            
            # Bar chart
            st.bar_chart(stats_df.set_index("Table")["Rows"])
    
    except Exception as e:
        st.error(f"Failed to load schema: {e}")


def main():
    if not check_auth():
        return
    
    st.title("🔐 YESOD Admin Dashboard")
    
    # Sidebar navigation
    page = st.sidebar.radio(
        "Navigation",
        ["📊 Overview", "👥 Users", "🔑 Sessions", "📋 Audit Logs", "⚡ Valkey Status", "🗄️ DB Schema", "🧪 API Test"]
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
    elif page == "📋 Audit Logs":
        show_audit_logs()
    elif page == "⚡ Valkey Status":
        show_valkey_status()
    elif page == "🗄️ DB Schema":
        show_db_schema()
    elif page == "🧪 API Test":
        show_api_test()


if __name__ == "__main__":
    main()
