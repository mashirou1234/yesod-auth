"""OAuth provider implementations."""
from typing import Optional
import httpx
from app.config import get_settings

settings = get_settings()


class GoogleOAuth:
    """Google OAuth implementation."""
    
    AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
    
    @classmethod
    def get_authorize_url(cls, redirect_uri: str, state: str) -> str:
        """Get the Google OAuth authorization URL."""
        params = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{cls.AUTHORIZE_URL}?{query}"
    
    @classmethod
    async def exchange_code(cls, code: str, redirect_uri: str) -> Optional[dict]:
        """Exchange authorization code for tokens."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                cls.TOKEN_URL,
                data={
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                },
            )
            if response.status_code == 200:
                return response.json()
            return None
    
    @classmethod
    async def get_user_info(cls, access_token: str) -> Optional[dict]:
        """Get user info from Google."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                cls.USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if response.status_code == 200:
                return response.json()
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
    async def exchange_code(cls, code: str, redirect_uri: str) -> Optional[dict]:
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
    async def get_user_info(cls, access_token: str) -> Optional[dict]:
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
                    data["avatar_url"] = f"https://cdn.discordapp.com/avatars/{data['id']}/{data['avatar']}.png"
                return data
            return None
