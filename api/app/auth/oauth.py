"""OAuth provider implementations."""

import httpx

from app.config import get_settings

settings = get_settings()


class GoogleOAuth:
    """Google OAuth implementation with PKCE support."""

    AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

    @classmethod
    def get_authorize_url(
        cls,
        redirect_uri: str,
        state: str,
        code_challenge: str | None = None,
    ) -> str:
        """Get the Google OAuth authorization URL with optional PKCE."""
        params = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }
        if code_challenge:
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = "S256"

        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{cls.AUTHORIZE_URL}?{query}"

    @classmethod
    async def exchange_code(
        cls,
        code: str,
        redirect_uri: str,
        code_verifier: str | None = None,
    ) -> dict | None:
        """Exchange authorization code for tokens."""
        data = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        }
        if code_verifier:
            data["code_verifier"] = code_verifier

        async with httpx.AsyncClient() as client:
            response = await client.post(cls.TOKEN_URL, data=data)
            if response.status_code == 200:
                return response.json()
            return None

    @classmethod
    async def get_user_info(cls, access_token: str) -> dict | None:
        """Get user info from Google."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                cls.USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if response.status_code == 200:
                return response.json()
            return None


class GitHubOAuth:
    """GitHub OAuth implementation with PKCE support."""

    AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
    TOKEN_URL = "https://github.com/login/oauth/access_token"
    USERINFO_URL = "https://api.github.com/user"
    EMAILS_URL = "https://api.github.com/user/emails"

    @classmethod
    def get_authorize_url(
        cls,
        redirect_uri: str,
        state: str,
        code_challenge: str | None = None,
    ) -> str:
        """Get the GitHub OAuth authorization URL with optional PKCE."""
        params = {
            "client_id": settings.GITHUB_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "scope": "read:user user:email",
            "state": state,
        }
        if code_challenge:
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = "S256"

        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{cls.AUTHORIZE_URL}?{query}"

    @classmethod
    async def exchange_code(
        cls,
        code: str,
        redirect_uri: str,
        code_verifier: str | None = None,
    ) -> dict | None:
        """Exchange authorization code for tokens."""
        data = {
            "client_id": settings.GITHUB_CLIENT_ID,
            "client_secret": settings.GITHUB_CLIENT_SECRET,
            "code": code,
            "redirect_uri": redirect_uri,
        }
        if code_verifier:
            data["code_verifier"] = code_verifier

        async with httpx.AsyncClient() as client:
            response = await client.post(
                cls.TOKEN_URL,
                data=data,
                headers={"Accept": "application/json"},
            )
            if response.status_code == 200:
                return response.json()
            return None

    @classmethod
    async def get_user_info(cls, access_token: str) -> dict | None:
        """Get user info from GitHub."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                cls.USERINFO_URL,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github+json",
                },
            )
            if response.status_code != 200:
                return None

            user_data = response.json()

            # If email is not public, fetch from emails API
            if not user_data.get("email"):
                email = await cls._get_primary_email(access_token)
                if email:
                    user_data["email"] = email

            return user_data

    @classmethod
    async def _get_primary_email(cls, access_token: str) -> str | None:
        """Get primary email from GitHub emails API."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                cls.EMAILS_URL,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github+json",
                },
            )
            if response.status_code != 200:
                return None

            emails = response.json()
            # Find primary verified email
            for email_data in emails:
                if email_data.get("primary") and email_data.get("verified"):
                    return email_data.get("email")

            # Fallback to first verified email
            for email_data in emails:
                if email_data.get("verified"):
                    return email_data.get("email")

            return None


class DiscordOAuth:
    """Discord OAuth implementation."""

    AUTHORIZE_URL = "https://discord.com/api/oauth2/authorize"
    TOKEN_URL = "https://discord.com/api/oauth2/token"
    USERINFO_URL = "https://discord.com/api/users/@me"

    @classmethod
    def get_authorize_url(cls, redirect_uri: str, state: str) -> str:
        """Get the Discord OAuth authorization URL."""
        params = {
            "client_id": settings.DISCORD_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "identify email",
            "state": state,
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{cls.AUTHORIZE_URL}?{query}"

    @classmethod
    async def exchange_code(cls, code: str, redirect_uri: str) -> dict | None:
        """Exchange authorization code for tokens."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                cls.TOKEN_URL,
                data={
                    "client_id": settings.DISCORD_CLIENT_ID,
                    "client_secret": settings.DISCORD_CLIENT_SECRET,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if response.status_code == 200:
                return response.json()
            return None

    @classmethod
    async def get_user_info(cls, access_token: str) -> dict | None:
        """Get user info from Discord."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                cls.USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if response.status_code == 200:
                data = response.json()
                # Add avatar URL
                if data.get("avatar"):
                    data["avatar_url"] = (
                        f"https://cdn.discordapp.com/avatars/{data['id']}/{data['avatar']}.png"
                    )
                return data
            return None


class XOAuth:
    """X (Twitter) OAuth 2.0 implementation with PKCE (required)."""

    AUTHORIZE_URL = "https://twitter.com/i/oauth2/authorize"
    TOKEN_URL = "https://api.twitter.com/2/oauth2/token"
    USERINFO_URL = "https://api.twitter.com/2/users/me"

    @classmethod
    def get_authorize_url(
        cls,
        redirect_uri: str,
        state: str,
        code_challenge: str,
    ) -> str:
        """Get the X OAuth authorization URL with PKCE (required for X)."""
        params = {
            "client_id": settings.X_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "tweet.read users.read offline.access",
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{cls.AUTHORIZE_URL}?{query}"

    @classmethod
    async def exchange_code(
        cls,
        code: str,
        redirect_uri: str,
        code_verifier: str,
    ) -> dict | None:
        """Exchange authorization code for tokens using Basic auth."""
        import base64

        # X requires Basic auth with client_id:client_secret
        credentials = f"{settings.X_CLIENT_ID}:{settings.X_CLIENT_SECRET}"
        encoded = base64.b64encode(credentials.encode()).decode()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                cls.TOKEN_URL,
                data={
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                    "code_verifier": code_verifier,
                },
                headers={
                    "Authorization": f"Basic {encoded}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
            if response.status_code == 200:
                return response.json()
            return None

    @classmethod
    async def get_user_info(cls, access_token: str) -> dict | None:
        """Get user info from X."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                cls.USERINFO_URL,
                params={"user.fields": "id,username,name,profile_image_url"},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if response.status_code == 200:
                data = response.json()
                # X API wraps user data in "data" field
                return data.get("data")
            return None
