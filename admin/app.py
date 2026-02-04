"""YESOD Admin Dashboard."""
import streamlit as st
import pandas as pd
import graphviz
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from config import settings
from i18n import (
    Translator,
    SUPPORTED_LANGUAGES,
    get_language_selector_options,
)
import db
import valkey_client

st.set_page_config(
    page_title="YESOD Admin",
    page_icon="🔐",
    layout="wide",
)


def get_translator() -> Translator:
    """Get translator instance based on session state."""
    if "language" not in st.session_state:
        st.session_state.language = settings.DEFAULT_LANGUAGE
    return Translator(st.session_state.language)


def generate_session_token(expiry: datetime) -> str:
    """Generate a secure session token with expiry."""
    expiry_ts = int(expiry.timestamp())
    message = f"{settings.ADMIN_USER}:{expiry_ts}"
    signature = hmac.new(
        settings.ADMIN_PASSWORD.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()[:32]
    return f"{expiry_ts}.{signature}"


def validate_session_token(token: str) -> bool:
    """Validate session token."""
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return False
        
        expiry_ts, signature = parts
        expiry_ts = int(expiry_ts)
        expiry = datetime.fromtimestamp(expiry_ts, tz=timezone.utc)
        
        # Check expiry
        if expiry < datetime.now(timezone.utc):
            return False
        
        # Verify signature
        message = f"{settings.ADMIN_USER}:{expiry_ts}"
        expected = hmac.new(
            settings.ADMIN_PASSWORD.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()[:32]
        
        return hmac.compare_digest(signature, expected)
    except (ValueError, TypeError):
        return False


def check_auth():
    """Authentication check with URL-based session persistence."""
    t = get_translator()

    # Initialize session state
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "session_token" not in st.session_state:
        st.session_state.session_token = None

    # Check for session token in query params
    token = st.query_params.get("session")

    if token and validate_session_token(token):
        st.session_state.authenticated = True
        st.session_state.session_token = token
        return True

    # Check session state (already authenticated in this session)
    if st.session_state.authenticated:
        if st.session_state.session_token and validate_session_token(st.session_state.session_token):
            return True
        # Token expired or invalid, but still in same session - allow access
        # (will need to re-login on next page load)
        return True

    # Show login form
    st.title(f"🔐 {t('app.login_title')}")

    with st.form("login"):
        username = st.text_input(t("login.username"))
        password = st.text_input(t("login.password"), type="password")
        remember = st.checkbox(t("login.remember_me"), value=True)
        submitted = st.form_submit_button(t("login.login_button"))

        if submitted:
            if username == settings.ADMIN_USER and password == settings.ADMIN_PASSWORD:
                st.session_state.authenticated = True

                if remember:
                    expiry = datetime.now(timezone.utc) + timedelta(hours=settings.SESSION_EXPIRY_HOURS)
                    token = generate_session_token(expiry)
                    st.session_state.session_token = token
                    # Set query param for persistence
                    st.query_params["session"] = token

                st.rerun()
            else:
                st.error(t("login.invalid_credentials"))

    # Show bookmark hint
    if st.session_state.get("session_token"):
        st.info(t("login.bookmark_tip"))

    return False


def show_overview():
    t = get_translator()
    st.header(t("overview.header"))

    try:
        stats = db.get_stats()

        col1, col2, col3 = st.columns(3)
        col1.metric(t("overview.total_users"), stats["total_users"])
        col2.metric(t("overview.oauth_accounts"), stats["total_oauth_accounts"])
        col3.metric(t("overview.active_sessions"), stats["active_sessions"])

    except Exception as e:
        st.error(f"{t('overview.failed_to_load')}: {e}")


def show_users():
    t = get_translator()
    st.header(t("users.header"))

    try:
        users_df = db.get_users()

        if users_df.empty:
            st.info(t("users.no_users"))
            return

        st.dataframe(
            users_df,
            use_container_width=True,
            hide_index=True,
        )

        # User details
        st.subheader(t("users.user_details"))
        user_ids = users_df["ID"].astype(str).tolist()
        selected_user = st.selectbox(t("users.select_user"), user_ids)

        if selected_user:
            col1, col2 = st.columns(2)

            with col1:
                st.write(f"**{t('users.oauth_accounts')}**")
                oauth_df = db.get_user_oauth_accounts(selected_user)
                if not oauth_df.empty:
                    st.dataframe(oauth_df, hide_index=True)
                else:
                    st.info(t("users.no_oauth"))

            with col2:
                st.write(f"**{t('users.actions')}**")
                if st.button(t("users.revoke_all_sessions"), key="revoke_all"):
                    count = db.revoke_all_user_sessions(selected_user)
                    st.success(t("users.revoked_sessions", count=count))
                    st.rerun()

    except Exception as e:
        st.error(f"{t('users.failed_to_load')}: {e}")


def show_sessions():
    t = get_translator()
    st.header(t("sessions.header"))

    try:
        sessions_df = db.get_sessions()

        if sessions_df.empty:
            st.info(t("sessions.no_sessions"))
            return

        # Filter options
        col1, col2 = st.columns(2)
        with col1:
            show_revoked = st.checkbox(t("sessions.show_revoked"), value=False)
        with col2:
            show_expired = st.checkbox(t("sessions.show_expired"), value=False)

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
        st.subheader(t("sessions.revoke_session"))
        session_ids = filtered_df["ID"].astype(str).tolist()
        if session_ids:
            selected_session = st.selectbox(t("sessions.select_session"), session_ids)
            if st.button(t("sessions.revoke_selected")):
                db.revoke_session(selected_session)
                st.success(t("sessions.session_revoked"))
                st.rerun()

    except Exception as e:
        st.error(f"{t('sessions.failed_to_load')}: {e}")


def show_valkey_status():
    t = get_translator()
    st.header(t("valkey.header"))

    try:
        # OAuth States
        st.subheader(t("valkey.oauth_states"))
        states = valkey_client.get_oauth_states()
        if states:
            st.dataframe(pd.DataFrame(states), hide_index=True)
        else:
            st.info(t("valkey.no_oauth_states"))

        # Rate Limits
        st.subheader(t("valkey.rate_limits"))
        limits = valkey_client.get_rate_limit_info()
        if limits:
            st.dataframe(pd.DataFrame(limits), hide_index=True)
        else:
            st.info(t("valkey.no_rate_limits"))

    except Exception as e:
        st.error(f"{t('valkey.failed_to_connect')}: {e}")


def show_audit_logs():
    t = get_translator()
    st.header(t("audit.header"))

    try:
        # Stats
        stats = db.get_audit_stats()

        col1, col2, col3 = st.columns(3)
        col1.metric(t("audit.logins_success"), stats["logins_success_24h"])
        col2.metric(t("audit.logins_failed"), stats["logins_failed_24h"])
        col3.metric(t("audit.events_24h"), stats["events_24h"])

        st.divider()

        # Tabs for different log types
        tab1, tab2 = st.tabs([t("audit.login_history_tab"), t("audit.auth_events_tab")])

        with tab1:
            st.subheader(t("audit.login_history"))

            login_df = db.get_login_history(100)
            if login_df.empty:
                st.info(t("audit.no_login_history"))
            else:
                # Filter options
                col1, col2 = st.columns(2)
                with col1:
                    show_success = st.checkbox(t("audit.show_successful"), value=True, key="login_success")
                with col2:
                    show_failed = st.checkbox(t("audit.show_failed"), value=True, key="login_failed")

                filtered_df = login_df.copy()
                if not show_success:
                    filtered_df = filtered_df[filtered_df["Success"] == False]
                if not show_failed:
                    filtered_df = filtered_df[filtered_df["Success"] == True]

                st.dataframe(filtered_df, use_container_width=True, hide_index=True)

        with tab2:
            st.subheader(t("audit.auth_events"))

            events_df = db.get_auth_events(100)
            if events_df.empty:
                st.info(t("audit.no_auth_events"))
            else:
                # Filter by event type
                event_types = events_df["Event Type"].unique().tolist()
                selected_types = st.multiselect(
                    t("audit.filter_by_type"),
                    event_types,
                    default=event_types,
                )

                filtered_df = events_df[events_df["Event Type"].isin(selected_types)]
                st.dataframe(filtered_df, use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"{t('audit.failed_to_load')}: {e}")


def show_api_test():
    t = get_translator()
    st.header(t("api_test.header"))

    API_BASE = "http://localhost:8000/api/v1"  # Use localhost for browser access

    # Token management
    st.subheader(t("api_test.get_token"))

    st.markdown(f"""
    {t("api_test.step1")}

    {t("api_test.step2")}

    {t("api_test.step3")}
    """)
    
    st.markdown(f"""
    <div style="display: flex; flex-wrap: wrap; gap: 12px; margin: 20px 0;">
        <a href="{API_BASE}/auth/google" target="_blank" 
           style="background: #4285f4; color: white; padding: 10px 20px; 
                  border-radius: 8px; text-decoration: none; font-weight: bold;">
            🔵 Google
        </a>
        <a href="{API_BASE}/auth/github" target="_blank"
           style="background: #333; color: white; padding: 10px 20px;
                  border-radius: 8px; text-decoration: none; font-weight: bold;">
            ⚫ GitHub
        </a>
        <a href="{API_BASE}/auth/discord" target="_blank"
           style="background: #5865f2; color: white; padding: 10px 20px;
                  border-radius: 8px; text-decoration: none; font-weight: bold;">
            🟣 Discord
        </a>
        <a href="{API_BASE}/auth/x" target="_blank"
           style="background: #000; color: white; padding: 10px 20px;
                  border-radius: 8px; text-decoration: none; font-weight: bold;">
            ✖️ X
        </a>
        <a href="{API_BASE}/auth/linkedin" target="_blank"
           style="background: #0077b5; color: white; padding: 10px 20px;
                  border-radius: 8px; text-decoration: none; font-weight: bold;">
            🔷 LinkedIn
        </a>
        <a href="{API_BASE}/auth/facebook" target="_blank"
           style="background: #1877f2; color: white; padding: 10px 20px;
                  border-radius: 8px; text-decoration: none; font-weight: bold;">
            🔵 Facebook
        </a>
        <a href="{API_BASE}/auth/slack" target="_blank"
           style="background: #4a154b; color: white; padding: 10px 20px;
                  border-radius: 8px; text-decoration: none; font-weight: bold;">
            💬 Slack
        </a>
        <a href="{API_BASE}/auth/twitch" target="_blank"
           style="background: #9146ff; color: white; padding: 10px 20px;
                  border-radius: 8px; text-decoration: none; font-weight: bold;">
            🎮 Twitch
        </a>
    </div>
    """, unsafe_allow_html=True)
    
    st.info(f"{t('api_test.buttons_hint')}\n\n"
            f"Google: {API_BASE}/auth/google\n\n"
            f"GitHub: {API_BASE}/auth/github\n\n"
            f"Discord: {API_BASE}/auth/discord")

    st.divider()

    st.subheader(t("api_test.enter_tokens"))

    if "test_access_token" not in st.session_state:
        st.session_state.test_access_token = ""
    if "test_refresh_token" not in st.session_state:
        st.session_state.test_refresh_token = ""

    col1, col2 = st.columns(2)
    with col1:
        st.session_state.test_access_token = st.text_input(
            t("api_test.access_token"),
            value=st.session_state.test_access_token,
            type="password",
        )
    with col2:
        st.session_state.test_refresh_token = st.text_input(
            t("api_test.refresh_token"),
            value=st.session_state.test_refresh_token,
            type="password",
        )

    st.divider()

    st.subheader(t("api_test.test_apis"))

    # Test sections (Delete Account removed for safety)
    tab1, tab2, tab3 = st.tabs([
        t("api_test.user_profile_tab"), t("api_test.account_link_tab"), t("api_test.sessions_tab")
    ])
    
    headers = {"Authorization": f"Bearer {st.session_state.test_access_token}"}
    
    # Use internal Docker network for API calls
    API_INTERNAL = "http://api:8000/api/v1"
    
    with tab1:
        st.subheader(t("api_test.user_profile_mgmt"))

        if st.button("GET /users/me", key="get_user"):
            try:
                import requests
                resp = requests.get(f"{API_INTERNAL}/users/me", headers=headers)
                st.json(resp.json())
                st.write(f"{t('common.status')}: {resp.status_code}")
            except Exception as e:
                st.error(f"{t('api_test.error')}: {e}")

        st.divider()

        st.write(f"**{t('api_test.update_profile')}**")
        new_display_name = st.text_input(t("api_test.new_display_name"), key="new_name")
        new_avatar_url = st.text_input(t("api_test.new_avatar_url"), key="new_avatar")

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
                st.write(f"{t('common.status')}: {resp.status_code}")
            except Exception as e:
                st.error(f"{t('api_test.error')}: {e}")

        st.divider()

        st.write(f"**{t('api_test.sync_from_provider')}**")
        st.caption(t("api_test.sync_caption"))
        sync_provider = st.selectbox(
            t("api_test.provider"),
            ["google", "github", "discord", "x", "linkedin", "facebook", "slack", "twitch"],
            key="sync_prov",
        )

        if st.button(f"POST /users/me/sync-from-provider?provider={sync_provider}", key="sync_profile"):
            try:
                import requests
                resp = requests.post(
                    f"{API_INTERNAL}/users/me/sync-from-provider?provider={sync_provider}",
                    headers=headers,
                )
                st.json(resp.json())
                st.write(f"{t('common.status')}: {resp.status_code}")
            except Exception as e:
                st.error(f"{t('api_test.error')}: {e}")
    
    with tab2:
        st.subheader(t("api_test.oauth_linking"))

        if st.button("GET /accounts", key="list_accounts"):
            try:
                import requests
                resp = requests.get(f"{API_INTERNAL}/accounts", headers=headers)
                st.json(resp.json())
                st.write(f"{t('common.status')}: {resp.status_code}")
            except Exception as e:
                st.error(f"{t('api_test.error')}: {e}")

        st.divider()

        st.write(f"**{t('api_test.link_new_provider')}**")
        st.caption(t("api_test.link_caption"))
        
        st.markdown(f"""
        <div style="display: flex; flex-wrap: wrap; gap: 12px; margin: 20px 0;">
            <a href="{API_BASE}/accounts/link/google" target="_blank" 
               style="background: #4285f4; color: white; padding: 10px 20px; 
                      border-radius: 8px; text-decoration: none; font-weight: bold;">
                🔵 Link Google
            </a>
            <a href="{API_BASE}/accounts/link/github" target="_blank"
               style="background: #333; color: white; padding: 10px 20px;
                      border-radius: 8px; text-decoration: none; font-weight: bold;">
                ⚫ Link GitHub
            </a>
            <a href="{API_BASE}/accounts/link/discord" target="_blank"
               style="background: #5865f2; color: white; padding: 10px 20px;
                      border-radius: 8px; text-decoration: none; font-weight: bold;">
                🟣 Link Discord
            </a>
            <a href="{API_BASE}/accounts/link/x" target="_blank"
               style="background: #000; color: white; padding: 10px 20px;
                      border-radius: 8px; text-decoration: none; font-weight: bold;">
                ✖️ Link X
            </a>
            <a href="{API_BASE}/accounts/link/linkedin" target="_blank"
               style="background: #0077b5; color: white; padding: 10px 20px;
                      border-radius: 8px; text-decoration: none; font-weight: bold;">
                🔷 Link LinkedIn
            </a>
            <a href="{API_BASE}/accounts/link/facebook" target="_blank"
               style="background: #1877f2; color: white; padding: 10px 20px;
                      border-radius: 8px; text-decoration: none; font-weight: bold;">
                🔵 Link Facebook
            </a>
            <a href="{API_BASE}/accounts/link/slack" target="_blank"
               style="background: #4a154b; color: white; padding: 10px 20px;
                      border-radius: 8px; text-decoration: none; font-weight: bold;">
                💬 Link Slack
            </a>
            <a href="{API_BASE}/accounts/link/twitch" target="_blank"
               style="background: #9146ff; color: white; padding: 10px 20px;
                      border-radius: 8px; text-decoration: none; font-weight: bold;">
                🎮 Link Twitch
            </a>
        </div>
        """, unsafe_allow_html=True)
        
        st.divider()

        st.write(f"**{t('api_test.unlink_provider')}**")
        unlink_provider = st.selectbox(
            t("api_test.provider_to_unlink"),
            ["google", "github", "discord", "x", "linkedin", "facebook", "slack", "twitch"],
            key="unlink_prov",
        )

        if st.button(f"DELETE /accounts/{unlink_provider}", key="unlink"):
            try:
                import requests
                resp = requests.delete(
                    f"{API_INTERNAL}/accounts/{unlink_provider}",
                    headers=headers,
                )
                st.json(resp.json())
                st.write(f"{t('common.status')}: {resp.status_code}")
            except Exception as e:
                st.error(f"{t('api_test.error')}: {e}")
    
    with tab3:
        st.subheader(t("api_test.session_mgmt"))

        if st.button("GET /sessions", key="list_sessions"):
            try:
                import requests
                resp = requests.get(f"{API_INTERNAL}/sessions", headers=headers)
                data = resp.json()
                st.json(data)
                st.write(f"{t('common.status')}: {resp.status_code}")

                if "sessions" in data:
                    st.session_state.session_ids = [s["id"] for s in data["sessions"]]
            except Exception as e:
                st.error(f"{t('api_test.error')}: {e}")

        st.divider()

        st.write(f"**{t('api_test.revoke_specific')}**")
        session_id = st.text_input(t("api_test.session_id_to_revoke"), key="revoke_session_id")

        if st.button("DELETE /sessions/{id}", key="revoke_one"):
            if session_id:
                try:
                    import requests
                    resp = requests.delete(
                        f"{API_INTERNAL}/sessions/{session_id}",
                        headers=headers,
                    )
                    st.json(resp.json())
                    st.write(f"{t('common.status')}: {resp.status_code}")
                except Exception as e:
                    st.error(f"{t('api_test.error')}: {e}")
            else:
                st.warning(t("api_test.enter_session_id"))

        st.divider()

        if st.button(f"DELETE /sessions ({t('api_test.revoke_all')})", key="revoke_all_sessions"):
            try:
                import requests
                resp = requests.delete(f"{API_INTERNAL}/sessions", headers=headers)
                st.json(resp.json())
                st.write(f"{t('common.status')}: {resp.status_code}")
            except Exception as e:
                st.error(f"{t('api_test.error')}: {e}")


def show_db_schema():
    t = get_translator()
    st.header(t("db_schema.header"))

    try:
        table_info = db.get_table_info()
        relationships = db.get_table_relationships()

        # Tab layout
        tab1, tab2, tab3 = st.tabs([t("db_schema.er_diagram_tab"), t("db_schema.tables_tab"), t("db_schema.statistics_tab")])

        with tab1:
            st.subheader(t("db_schema.er_diagram"))
            
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
            st.markdown(f"""
            **{t("db_schema.legend")}:**
            - {t("db_schema.legend_pk")}
            - {t("db_schema.legend_fk")}
            - {t("db_schema.legend_core")}
            - {t("db_schema.legend_user_related")}
            - {t("db_schema.legend_deleted")}
            - {t("db_schema.legend_other")}
            """)
        
        with tab2:
            st.subheader(t("db_schema.table_details"))

            # Table selector
            selected_table = st.selectbox(
                t("db_schema.select_table"),
                list(table_info.keys()),
            )

            if selected_table:
                info = table_info[selected_table]

                col1, col2 = st.columns([2, 1])

                with col1:
                    st.write(f"**{t('db_schema.columns')}**")
                    cols_df = pd.DataFrame(info["columns"])
                    cols_df["PK"] = cols_df["name"].isin(info["primary_keys"])
                    fk_cols = {fk["column"] for fk in info["foreign_keys"]}
                    cols_df["FK"] = cols_df["name"].isin(fk_cols)
                    st.dataframe(cols_df, hide_index=True, use_container_width=True)

                with col2:
                    st.write(f"**{t('db_schema.info')}**")
                    st.metric(t("db_schema.row_count"), info["row_count"])

                    if info["foreign_keys"]:
                        st.write(f"**{t('db_schema.foreign_keys')}**")
                        for fk in info["foreign_keys"]:
                            st.write(f"- `{fk['column']}` → `{fk['references_table']}.{fk['references_column']}`")
        
        with tab3:
            st.subheader(t("db_schema.db_statistics"))

            # Summary metrics
            total_tables = len(table_info)
            total_rows = sum(info["row_count"] for info in table_info.values())
            total_relationships = len(relationships)

            col1, col2, col3 = st.columns(3)
            col1.metric(t("db_schema.total_tables"), total_tables)
            col2.metric(t("db_schema.total_rows"), total_rows)
            col3.metric(t("db_schema.relationships"), total_relationships)

            st.divider()

            # Row counts per table
            st.write(f"**{t('db_schema.rows_per_table')}**")
            stats_data = [
                {"Table": name, "Rows": info["row_count"], "Columns": len(info["columns"])}
                for name, info in table_info.items()
            ]
            stats_df = pd.DataFrame(stats_data).sort_values("Rows", ascending=False)
            st.dataframe(stats_df, hide_index=True, use_container_width=True)

            # Bar chart
            st.bar_chart(stats_df.set_index("Table")["Rows"])

    except Exception as e:
        st.error(f"{t('db_schema.failed_to_load')}: {e}")


def main():
    if not check_auth():
        return

    t = get_translator()

    # Environment badge (only show in non-production environments)
    if settings.ENVIRONMENT:
        env_colors = {
            "CI": "#f44336",      # Red
            "DEV": "#ff9800",     # Orange
            "STAGING": "#2196f3", # Blue
        }
        env_name = settings.ENVIRONMENT.upper()
        color = env_colors.get(env_name, "#9e9e9e")
        st.markdown(
            f'<div style="background: {color}; color: white; padding: 8px 16px; '
            f'border-radius: 6px; font-weight: bold; font-size: 18px; '
            f'text-align: center; margin-bottom: 16px;">{t("common.environment_warning", env=env_name)}</div>',
            unsafe_allow_html=True,
        )

    st.title(f"🔐 {t('app.title')}")

    # Sidebar - Language selector
    st.sidebar.markdown(f"### {t('nav.language')}")
    lang_options = get_language_selector_options()
    current_lang_display = SUPPORTED_LANGUAGES.get(st.session_state.language, "English")
    selected_lang_display = st.sidebar.selectbox(
        t("nav.language"),
        list(lang_options.keys()),
        index=list(lang_options.keys()).index(current_lang_display),
        label_visibility="collapsed",
    )
    if lang_options[selected_lang_display] != st.session_state.language:
        st.session_state.language = lang_options[selected_lang_display]
        st.rerun()

    st.sidebar.divider()

    # Sidebar navigation
    page = st.sidebar.radio(
        t("nav.navigation"),
        [t("nav.overview"), t("nav.users"), t("nav.sessions"), t("nav.audit_logs"), t("nav.valkey_status"), t("nav.db_schema"), t("nav.api_test")]
    )

    if st.sidebar.button(t("nav.refresh")):
        st.rerun()

    if st.sidebar.button(t("nav.logout")):
        st.session_state.authenticated = False
        st.session_state.session_token = None
        st.query_params.clear()
        st.rerun()

    if page == t("nav.overview"):
        show_overview()
    elif page == t("nav.users"):
        show_users()
    elif page == t("nav.sessions"):
        show_sessions()
    elif page == t("nav.audit_logs"):
        show_audit_logs()
    elif page == t("nav.valkey_status"):
        show_valkey_status()
    elif page == t("nav.db_schema"):
        show_db_schema()
    elif page == t("nav.api_test"):
        show_api_test()


if __name__ == "__main__":
    main()
