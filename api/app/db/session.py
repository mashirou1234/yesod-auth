"""Database session management."""

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db.base import DEFAULT_PROJECT_ID
from app.db.project import ProjectAsyncSession

settings = get_settings()

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=ProjectAsyncSession,
    expire_on_commit=False,
)


# Explicit default-project factory for the existing worker.
def async_session_factory():
    """The existing webhook worker owns only the default project."""
    return async_session_maker(project_id=DEFAULT_PROJECT_ID)


async def get_db():
    """Dependency for getting database session."""
    async with async_session_maker(project_id=DEFAULT_PROJECT_ID) as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
