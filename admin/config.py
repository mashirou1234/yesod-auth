"""Admin configuration."""
import os


def read_secret(name: str, default: str = "") -> str:
    """Read secret from Docker secrets or environment variable."""
    secret_path = f"/run/secrets/{name}"
    if os.path.exists(secret_path):
        with open(secret_path, "r") as f:
            return f.read().strip()
    return os.getenv(name.upper(), default)


class Settings:
    # Use sync driver (psycopg2) for Streamlit
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://yesod_user:yesod_password@localhost:5432/yesod"
    )
    VALKEY_URL: str = os.getenv("VALKEY_URL", "redis://localhost:6379/0")
    ADMIN_USER: str = os.getenv("ADMIN_USER", "admin")
    ADMIN_PASSWORD: str = read_secret("admin_password", "admin")
    
    # Environment indicator (empty = production, otherwise shows badge)
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "")


settings = Settings()
