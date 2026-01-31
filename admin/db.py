"""Database operations for admin (sync version)."""
from typing import Optional
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import pandas as pd

from config import settings

engine = create_engine(settings.DATABASE_URL)
Session = sessionmaker(bind=engine)


def get_users() -> pd.DataFrame:
    with Session() as session:
        result = session.execute(text("""
            SELECT 
                u.id,
                u.email,
                u.display_name,
                u.created_at,
                u.updated_at,
                COUNT(DISTINCT oa.id) as oauth_accounts,
                COUNT(DISTINCT rt.id) FILTER (WHERE rt.is_revoked = false AND rt.expires_at > NOW()) as active_sessions
            FROM users u
            LEFT JOIN oauth_accounts oa ON u.id = oa.user_id
            LEFT JOIN refresh_tokens rt ON u.id = rt.user_id
            GROUP BY u.id
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
            WHERE user_id = :user_id
            ORDER BY created_at
        """), {"user_id": user_id})
        rows = result.fetchall()
        return pd.DataFrame(rows, columns=["Provider", "Provider User ID", "Created At"])


def get_sessions(user_id: Optional[str] = None) -> pd.DataFrame:
    with Session() as session:
        query = """
            SELECT 
                rt.id,
                u.email,
                rt.device_info,
                rt.ip_address,
                rt.is_revoked,
                rt.expires_at,
                rt.created_at,
                rt.last_used_at
            FROM refresh_tokens rt
            JOIN users u ON rt.user_id = u.id
        """
        params = {}
        if user_id:
            query += " WHERE rt.user_id = :user_id"
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
        session.execute(text("""
            UPDATE refresh_tokens SET is_revoked = true WHERE id = :id
        """), {"id": session_id})
        session.commit()
        return True


def revoke_all_user_sessions(user_id: str) -> int:
    with Session() as session:
        result = session.execute(text("""
            UPDATE refresh_tokens 
            SET is_revoked = true 
            WHERE user_id = :user_id AND is_revoked = false
            RETURNING id
        """), {"user_id": user_id})
        session.commit()
        return len(result.fetchall())


def get_stats() -> dict:
    with Session() as session:
        users = session.execute(text("SELECT COUNT(*) FROM users"))
        oauth = session.execute(text("SELECT COUNT(*) FROM oauth_accounts"))
        active_sessions = session.execute(text("""
            SELECT COUNT(*) FROM refresh_tokens 
            WHERE is_revoked = false AND expires_at > NOW()
        """))
        return {
            "total_users": users.scalar(),
            "total_oauth_accounts": oauth.scalar(),
            "active_sessions": active_sessions.scalar(),
        }
