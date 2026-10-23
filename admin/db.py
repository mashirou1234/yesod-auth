"""Database operations for admin (sync version)."""
from typing import Optional
import uuid
from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import Session as SASession
from sqlalchemy.orm import sessionmaker
import pandas as pd

from config import settings

engine = create_engine(settings.DATABASE_URL)
DEFAULT_PROJECT_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")


class DefaultProjectSession(SASession):
    def execute(self, statement, params=None, **kwargs):
        values = dict(params or {})
        if "project_id" in values and str(values["project_id"]) != str(DEFAULT_PROJECT_ID):
            raise ValueError("Admin project substitution is forbidden")
        values["project_id"] = str(DEFAULT_PROJECT_ID)
        return super().execute(statement, values, **kwargs)


@event.listens_for(DefaultProjectSession, "after_begin")
def _bind_admin_project(session, transaction, connection):
    connection.execute(text("SELECT set_config('yesod.project_id', :project_id, true)"),
                       {"project_id": str(DEFAULT_PROJECT_ID)})


Session = sessionmaker(bind=engine, class_=DefaultProjectSession)


def get_users() -> pd.DataFrame:
    with Session() as session:
        result = session.execute(text("""
            SELECT 
                u.id,
                ue.email,
                up.display_name,
                u.created_at,
                up.updated_at,
                COUNT(DISTINCT oa.id) as oauth_accounts,
                COUNT(DISTINCT rt.id) FILTER (WHERE rt.is_revoked = false AND rt.expires_at > NOW()) as active_sessions
            FROM users u
            LEFT JOIN user_emails ue ON u.id = ue.user_id AND u.project_id = ue.project_id AND ue.is_primary = true
            LEFT JOIN user_profiles up ON u.id = up.user_id AND u.project_id = up.project_id
            LEFT JOIN oauth_accounts oa ON u.id = oa.user_id AND u.project_id = oa.project_id
            LEFT JOIN refresh_tokens rt ON u.id = rt.user_id AND u.project_id = rt.project_id
            WHERE u.project_id = :project_id
            GROUP BY u.id, ue.email, up.display_name, up.updated_at
            ORDER BY u.created_at DESC
        """))
        rows = result.fetchall()
        return pd.DataFrame(rows, columns=[
            "ID", "Email", "Display Name", "Created At", "Updated At", 
            "OAuth Accounts", "Active Sessions"
        ])


def get_user_oauth_accounts(user_id: str) -> pd.DataFrame:
    with Session() as session:
        result = session.execute(text("""
            SELECT provider, provider_user_id, created_at
            FROM oauth_accounts
            WHERE project_id = :project_id AND user_id = :user_id
            ORDER BY created_at
        """), {"user_id": user_id})
        rows = result.fetchall()
        return pd.DataFrame(rows, columns=["Provider", "Provider User ID", "Created At"])


def get_sessions(user_id: Optional[str] = None) -> pd.DataFrame:
    with Session() as session:
        query = """
            SELECT 
                rt.id,
                ue.email,
                rt.device_info,
                rt.ip_address,
                rt.is_revoked,
                rt.expires_at,
                rt.created_at,
                rt.last_used_at
            FROM refresh_tokens rt
            JOIN users u ON rt.user_id = u.id AND rt.project_id = u.project_id
            LEFT JOIN user_emails ue ON u.id = ue.user_id AND u.project_id = ue.project_id AND ue.is_primary = true
        """
        query += " WHERE rt.project_id = :project_id"
        params = {}
        if user_id:
            query += " AND rt.user_id = :user_id"
            params["user_id"] = user_id
        query += " ORDER BY rt.created_at DESC LIMIT 100"
        
        result = session.execute(text(query), params)
        rows = result.fetchall()
        return pd.DataFrame(rows, columns=[
            "ID", "User Email", "Device", "IP Address", 
            "Revoked", "Expires At", "Created At", "Last Used"
        ])


def revoke_session(session_id: str) -> bool:
    with Session() as session:
        result = session.execute(text("""
            UPDATE refresh_tokens SET is_revoked = true WHERE project_id = :project_id AND id = :id
        """), {"id": session_id})
        session.commit()
        return result.rowcount > 0


def revoke_all_user_sessions(user_id: str) -> int:
    with Session() as session:
        result = session.execute(text("""
            UPDATE refresh_tokens 
            SET is_revoked = true 
            WHERE project_id = :project_id AND user_id = :user_id AND is_revoked = false
            RETURNING id
        """), {"user_id": user_id})
        session.commit()
        return len(result.fetchall())


def get_stats() -> dict:
    with Session() as session:
        users = session.execute(text("SELECT COUNT(*) FROM users WHERE project_id = :project_id"))
        oauth = session.execute(text("SELECT COUNT(*) FROM oauth_accounts WHERE project_id = :project_id"))
        active_sessions = session.execute(text("""
            SELECT COUNT(*) FROM refresh_tokens 
            WHERE project_id = :project_id AND is_revoked = false AND expires_at > NOW()
        """))
        return {
            "total_users": users.scalar(),
            "total_oauth_accounts": oauth.scalar(),
            "active_sessions": active_sessions.scalar(),
        }


def get_deleted_users() -> pd.DataFrame:
    """Get soft-deleted users pending purge."""
    with Session() as session:
        result = session.execute(text("""
            SELECT 
                id,
                email_backup,
                display_name_backup,
                deleted_at,
                purge_at,
                oauth_providers
            FROM deleted_users
            WHERE project_id = :project_id
            ORDER BY deleted_at DESC
        """))
        rows = result.fetchall()
        return pd.DataFrame(rows, columns=[
            "ID", "Email", "Display Name", "Deleted At", "Purge At", "OAuth Providers"
        ])


def get_table_info() -> dict:
    """Get detailed information about all tables."""
    with Session() as session:
        # Get all tables
        tables_result = session.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """))
        tables = [row[0] for row in tables_result.fetchall()]
        
        table_info = {}
        for table in tables:
            # Get columns
            cols_result = session.execute(text("""
                SELECT 
                    column_name,
                    data_type,
                    is_nullable,
                    column_default
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = :table
                ORDER BY ordinal_position
            """), {"table": table})
            
            columns = []
            for row in cols_result.fetchall():
                columns.append({
                    "name": row[0],
                    "type": row[1],
                    "nullable": row[2] == "YES",
                    "default": row[3],
                })
            
            # Get primary keys
            pk_result = session.execute(text("""
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu 
                    ON tc.constraint_name = kcu.constraint_name
                WHERE tc.table_schema = 'public' 
                    AND tc.table_name = :table 
                    AND tc.constraint_type = 'PRIMARY KEY'
            """), {"table": table})
            primary_keys = [row[0] for row in pk_result.fetchall()]
            
            # Get foreign keys
            fk_result = session.execute(text("""
                SELECT 
                    kcu.column_name,
                    ccu.table_name AS foreign_table,
                    ccu.column_name AS foreign_column
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu 
                    ON tc.constraint_name = kcu.constraint_name
                JOIN information_schema.constraint_column_usage ccu 
                    ON tc.constraint_name = ccu.constraint_name
                WHERE tc.table_schema = 'public' 
                    AND tc.table_name = :table 
                    AND tc.constraint_type = 'FOREIGN KEY'
            """), {"table": table})
            foreign_keys = []
            for row in fk_result.fetchall():
                foreign_keys.append({
                    "column": row[0],
                    "references_table": row[1],
                    "references_column": row[2],
                })
            
            # Get row count
            if table == "projects":
                predicate = " WHERE id = :project_id"
            elif "project_id" in {column["name"] for column in columns}:
                predicate = " WHERE project_id = :project_id"
            else:
                predicate = ""
            # Table names came from PostgreSQL metadata; quote identifiers through the dialect.
            quoted = engine.dialect.identifier_preparer.quote(table)
            count_result = session.execute(text(f"SELECT COUNT(*) FROM {quoted}{predicate}"))
            row_count = count_result.scalar()
            
            table_info[table] = {
                "columns": columns,
                "primary_keys": primary_keys,
                "foreign_keys": foreign_keys,
                "row_count": row_count,
            }
        
        return table_info


def get_table_relationships() -> list:
    """Get all foreign key relationships for ER diagram."""
    with Session() as session:
        result = session.execute(text("""
            SELECT 
                tc.table_name AS from_table,
                kcu.column_name AS from_column,
                ccu.table_name AS to_table,
                ccu.column_name AS to_column
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu 
                ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage ccu 
                ON tc.constraint_name = ccu.constraint_name
            WHERE tc.table_schema = 'public' 
                AND tc.constraint_type = 'FOREIGN KEY'
            ORDER BY tc.table_name
        """))
        
        relationships = []
        for row in result.fetchall():
            relationships.append({
                "from_table": row[0],
                "from_column": row[1],
                "to_table": row[2],
                "to_column": row[3],
            })
        
        return relationships


def get_login_history(limit: int = 100) -> pd.DataFrame:
    """Get recent login history from audit schema."""
    with Session() as session:
        try:
            result = session.execute(text("""
                SELECT 
                    id,
                    user_id,
                    provider,
                    ip_address,
                    user_agent,
                    success,
                    failure_reason,
                    created_at
                FROM audit.login_history
                WHERE project_id = :project_id
                ORDER BY created_at DESC
                LIMIT :limit
            """), {"limit": limit})
            rows = result.fetchall()
            return pd.DataFrame(rows, columns=[
                "ID", "User ID", "Provider", "IP Address", "User Agent",
                "Success", "Failure Reason", "Created At"
            ])
        except Exception:
            return pd.DataFrame()


def get_auth_events(limit: int = 100) -> pd.DataFrame:
    """Get recent auth events from audit schema."""
    with Session() as session:
        try:
            result = session.execute(text("""
                SELECT 
                    id,
                    user_id,
                    event_type,
                    details,
                    ip_address,
                    created_at
                FROM audit.auth_events
                WHERE project_id = :project_id
                ORDER BY created_at DESC
                LIMIT :limit
            """), {"limit": limit})
            rows = result.fetchall()
            return pd.DataFrame(rows, columns=[
                "ID", "User ID", "Event Type", "Details", "IP Address", "Created At"
            ])
        except Exception:
            return pd.DataFrame()


def get_audit_stats() -> dict:
    """Get audit statistics."""
    with Session() as session:
        try:
            # Logins last 24h
            logins_24h = session.execute(text("""
                SELECT 
                    COUNT(*) FILTER (WHERE success = true) as success,
                    COUNT(*) FILTER (WHERE success = false) as failed
                FROM audit.login_history
                WHERE project_id = :project_id AND created_at > NOW() - INTERVAL '24 hours'
            """))
            login_row = logins_24h.fetchone()
            
            # Events last 24h
            events_24h = session.execute(text("""
                SELECT COUNT(*) FROM audit.auth_events
                WHERE project_id = :project_id AND created_at > NOW() - INTERVAL '24 hours'
            """))
            
            return {
                "logins_success_24h": login_row[0] if login_row else 0,
                "logins_failed_24h": login_row[1] if login_row else 0,
                "events_24h": events_24h.scalar() or 0,
            }
        except Exception:
            return {
                "logins_success_24h": 0,
                "logins_failed_24h": 0,
                "events_24h": 0,
            }
