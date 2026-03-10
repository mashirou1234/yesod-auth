"""Prometheus metrics endpoint."""

from collections import defaultdict
from threading import Lock

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db

router = APIRouter(tags=["metrics"])
_oauth_failure_counts: dict[tuple[str, str], int] = defaultdict(int)
_oauth_failure_counts_lock = Lock()
_oauth_rate_limit_burst_counts: dict[str, int] = defaultdict(int)
_oauth_rate_limit_burst_counts_lock = Lock()


def record_oauth_failure_metric(provider: str, reason: str) -> None:
    """Record OAuth failure counter grouped by provider and failure reason."""
    with _oauth_failure_counts_lock:
        _oauth_failure_counts[(provider, reason)] += 1


def reset_oauth_failure_metrics() -> None:
    """Reset OAuth failure counters. Used by tests for deterministic assertions."""
    with _oauth_failure_counts_lock:
        _oauth_failure_counts.clear()


def render_oauth_failure_metrics_lines() -> list[str]:
    """Render OAuth failure metric lines from in-memory counters."""
    with _oauth_failure_counts_lock:
        oauth_failure_snapshot = dict(_oauth_failure_counts)
    return [
        f'yesod_oauth_failures_total{{provider="{provider}",reason="{reason}"}} {count}'
        for (provider, reason), count in sorted(oauth_failure_snapshot.items())
    ]


def record_oauth_rate_limit_burst_metric(provider: str) -> None:
    """Record OAuth burst rate-limit events grouped by provider."""
    with _oauth_rate_limit_burst_counts_lock:
        _oauth_rate_limit_burst_counts[provider] += 1


def reset_oauth_rate_limit_burst_metrics() -> None:
    """Reset OAuth burst rate-limit counters. Used by tests for deterministic assertions."""
    with _oauth_rate_limit_burst_counts_lock:
        _oauth_rate_limit_burst_counts.clear()


def render_oauth_rate_limit_burst_metrics_lines() -> list[str]:
    """Render OAuth burst rate-limit metric lines from in-memory counters."""
    with _oauth_rate_limit_burst_counts_lock:
        oauth_rate_limit_snapshot = dict(_oauth_rate_limit_burst_counts)
    return [
        f'yesod_oauth_rate_limit_burst_total{{provider="{provider}"}} {count}'
        for provider, count in sorted(oauth_rate_limit_snapshot.items())
    ]


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics(db: AsyncSession = Depends(get_db)):
    """Prometheus-compatible metrics endpoint."""

    metrics_output = []

    # User metrics
    result = await db.execute(text("SELECT COUNT(*) FROM users"))
    total_users = result.scalar()
    metrics_output.append(f"yesod_users_total {total_users}")

    # OAuth accounts
    result = await db.execute(text("SELECT COUNT(*) FROM oauth_accounts"))
    total_oauth = result.scalar()
    metrics_output.append(f"yesod_oauth_accounts_total {total_oauth}")

    # OAuth by provider
    result = await db.execute(
        text("""
        SELECT provider, COUNT(*) FROM oauth_accounts GROUP BY provider
    """)
    )
    for row in result.fetchall():
        metrics_output.append(f'yesod_oauth_accounts_by_provider{{provider="{row[0]}"}} {row[1]}')

    # Active sessions
    result = await db.execute(
        text("""
        SELECT COUNT(*) FROM refresh_tokens
        WHERE is_revoked = false AND expires_at > NOW()
    """)
    )
    active_sessions = result.scalar()
    metrics_output.append(f"yesod_active_sessions {active_sessions}")

    # Deleted users pending purge
    result = await db.execute(text("SELECT COUNT(*) FROM deleted_users"))
    deleted_users = result.scalar()
    metrics_output.append(f"yesod_deleted_users_pending {deleted_users}")

    metrics_output.extend(render_oauth_failure_metrics_lines())
    metrics_output.extend(render_oauth_rate_limit_burst_metrics_lines())

    # Login stats (last 24h) - only if audit schema exists
    try:
        result = await db.execute(
            text("""
            SELECT
                success,
                COUNT(*)
            FROM audit.login_history
            WHERE created_at > NOW() - INTERVAL '24 hours'
            GROUP BY success
        """)
        )
        for row in result.fetchall():
            status = "success" if row[0] else "failed"
            metrics_output.append(f'yesod_logins_24h{{status="{status}"}} {row[1]}')

        # Auth events (last 24h)
        result = await db.execute(
            text("""
            SELECT event_type, COUNT(*)
            FROM audit.auth_events
            WHERE created_at > NOW() - INTERVAL '24 hours'
            GROUP BY event_type
        """)
        )
        for row in result.fetchall():
            metrics_output.append(f'yesod_auth_events_24h{{event_type="{row[0]}"}} {row[1]}')
    except Exception:
        # Audit schema might not exist yet
        pass

    return "\n".join(metrics_output) + "\n"
