"""Mock OAuth for development and testing.

Enable by setting MOCK_OAUTH_ENABLED=1 environment variable.
This allows bypassing real OAuth providers during development.
"""

import os
import uuid
from dataclasses import dataclass


def is_mock_oauth_enabled() -> bool:
    """Check if mock OAuth is enabled."""
    return os.getenv("MOCK_OAUTH_ENABLED", "").lower() in ("1", "true", "yes")


@dataclass
class MockOAuthUser:
    """Mock OAuth user data."""

    id: str
    email: str
    name: str
    picture: str | None = None

    def to_google_format(self) -> dict:
        """Convert to Google userinfo format."""
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "picture": self.picture,
            "verified_email": True,
        }

    def to_discord_format(self) -> dict:
        """Convert to Discord userinfo format."""
        return {
            "id": self.id,
            "email": self.email,
            "username": self.name,
            "avatar": None,
            "avatar_url": self.picture,
        }

    def to_github_format(self) -> dict:
        """Convert to GitHub userinfo format."""
        # Generate a numeric ID from the mock ID
        numeric_id = int(self.id.split("-")[-1]) if "-" in self.id else 12345
        return {
            "id": numeric_id,
            "login": self.name.lower().replace(" ", ""),
            "name": self.name,
            "email": self.email,
            "avatar_url": self.picture,
        }

    def to_x_format(self) -> dict:
        """Convert to X (Twitter) userinfo format.

        Note: X API does not provide email addresses.
        A placeholder email is generated using the username.
        """
        username = self.name.lower().replace(" ", "_")
        return {
            "id": self.id,
            "username": username,
            "name": self.name,
            "profile_image_url": self.picture,
            # X doesn't provide email, generate placeholder
            "email": f"{username}@x.yesod-auth.local",
        }

    def to_linkedin_format(self) -> dict:
        """Convert to LinkedIn userinfo format (OpenID Connect)."""
        return {
            "sub": self.id,
            "name": self.name,
            "email": self.email,
            "picture": self.picture,
            "email_verified": True,
        }

    def to_facebook_format(self) -> dict:
        """Convert to Facebook Graph API userinfo format."""
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "picture": {
                "data": {
                    "url": self.picture,
                    "is_silhouette": False,
                }
            },
        }

    def to_slack_format(self) -> dict:
        """Convert to Slack OpenID Connect userinfo format."""
        return {
            "ok": True,
            "sub": self.id,
            "name": self.name,
            "email": self.email,
            "picture": self.picture,
            "email_verified": True,
        }

    def to_twitch_format(self) -> dict:
        """Convert to Twitch Helix API userinfo format."""
        login = self.name.lower().replace(" ", "_")
        return {
            "id": self.id,
            "login": login,
            "display_name": self.name,
            "email": self.email,
            "profile_image_url": self.picture,
            "broadcaster_type": "",
            "description": "",
            "type": "",
        }


# Predefined mock users for testing
MOCK_USERS = {
    "alice": MockOAuthUser(
        id="mock-alice-123",
        email="alice@example.com",
        name="Alice Developer",
        picture="https://api.dicebear.com/7.x/avataaars/svg?seed=alice",
    ),
    "bob": MockOAuthUser(
        id="mock-bob-456",
        email="bob@example.com",
        name="Bob Tester",
        picture="https://api.dicebear.com/7.x/avataaars/svg?seed=bob",
    ),
    "charlie": MockOAuthUser(
        id="mock-charlie-789",
        email="charlie@example.com",
        name="Charlie Admin",
        picture="https://api.dicebear.com/7.x/avataaars/svg?seed=charlie",
    ),
}


def get_mock_user(username: str = "alice") -> MockOAuthUser:
    """Get a mock user by username."""
    return MOCK_USERS.get(username, MOCK_USERS["alice"])


def create_custom_mock_user(
    email: str,
    name: str | None = None,
    picture: str | None = None,
) -> MockOAuthUser:
    """Create a custom mock user."""
    return MockOAuthUser(
        id=f"mock-{uuid.uuid4().hex[:8]}",
        email=email,
        name=name or email.split("@")[0],
        picture=picture or f"https://api.dicebear.com/7.x/avataaars/svg?seed={email}",
    )
