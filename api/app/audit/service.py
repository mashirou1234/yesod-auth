"""Audit logging service."""

import os
import uuid
from enum import StrEnum

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _is_testing() -> bool:
    """Check if running in test environment."""
    return os.environ.get("TESTING") == "1"


class AuthEventType(StrEnum):
    """Authentication event types."""

    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    TOKEN_REFRESH = "token_refresh"
    TOKEN_REFRESH_FAILED = "token_refresh_failed"
    ACCOUNT_LINKED = "account_linked"
    ACCOUNT_UNLINKED = "account_unlinked"
    PROFILE_UPDATED = "profile_updated"
    PROFILE_SYNCED = "profile_synced"
    ACCOUNT_DELETED = "account_deleted"
    SESSION_REVOKED = "session_revoked"
    ALL_SESSIONS_REVOKED = "all_sessions_revoked"


class AuditLogger:
    """Audit logging service for authentication events."""

    @staticmethod
    async def log_login(
        db: AsyncSession,
        user_id: uuid.UUID | None,
        provider: str,
        success: bool,
        ip_address: str | None = None,
        user_agent: str | None = None,
        failure_reason: str | None = None,
    ) -> None:
        """Log a login attempt."""
        if _is_testing():
            return  # Skip audit logging in test environment

        await db.execute(
            text("""
                INSERT INTO audit.login_history
                (user_id, provider, ip_address, user_agent, success, failure_reason)
                VALUES (:user_id, :provider, :ip_address, :user_agent, :success, :failure_reason)
            """),
            {
                "user_id": str(user_id) if user_id else None,
                "provider": provider,
                "ip_address": ip_address,
                "user_agent": user_agent[:500] if user_agent else None,
                "success": success,
                "failure_reason": failure_reason,
            },
        )
        await db.commit()

    @staticmethod
    async def log_event(
        db: AsyncSession,
        event_type: AuthEventType,
        user_id: uuid.UUID | None = None,
        details: dict | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Log an authentication event."""
        if _is_testing():
            return  # Skip audit logging in test environment

        import json

        await db.execute(
            text("""
                INSERT INTO audit.auth_events
                (user_id, event_type, details, ip_address, user_agent)
                VALUES (:user_id, :event_type, :details::jsonb, :ip_address, :user_agent)
            """),
            {
                "user_id": str(user_id) if user_id else None,
                "event_type": event_type.value,
                "details": json.dumps(details) if details else None,
                "ip_address": ip_address,
                "user_agent": user_agent[:500] if user_agent else None,
            },
        )
        await db.commit()
