"""OAuth provider implementations."""

import logging
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

_SENSITIVE_QUERY_KEYS = (
    "token",
    "secret",
    "code",
    "state",
    "nonce",
    "signature",
    "sig",
    "key",
)


def _mask_value(value: str, keep_prefix: int = 4) -> str:
    if not value:
        return ""
    if len(value) <= keep_prefix:
        return "*" * len(value)
    return f"{value[:keep_prefix]}***"


def _mask_query_value(key: str, value: str) -> str:
    lowered = key.lower()
    if any(marker in lowered for marker in _SENSITIVE_QUERY_KEYS):
        return _mask_value(value)
    return value


def _normalize_redirect_uri(redirect_uri: str) -> str:
    candidate = redirect_uri.strip()
    if not candidate:
        return candidate
    try:
        parsed = urlsplit(candidate)
    except ValueError:
        return candidate

    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower()
    port = parsed.port
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        netloc = f"{host}:{port}"
    else:
        netloc = host

    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    query = urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True)), doseq=True)
    return urlunsplit((scheme, netloc, path, query, ""))


def _mask_redirect_uri_for_log(redirect_uri: str) -> str:
    if not redirect_uri:
        return ""
    try:
        parsed = urlsplit(redirect_uri)
    except ValueError:
        return _mask_value(redirect_uri)
    masked_query = urlencode(
        [(k, _mask_query_value(k, v)) for k, v in parse_qsl(parsed.query, keep_blank_values=True)],
        doseq=True,
    )
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, masked_query, ""))


def _sanitize_error_snippet(text: str | None) -> str:
    if not text:
        return ""
    compact = " ".join(text.split())
    compact = re.sub(
        r"(?i)(client_secret|access_token|refresh_token|id_token|code)=([^&\s]+)",
        r"\1=***",
        compact,
    )
    compact = re.sub(
        r'(?i)"(client_secret|access_token|refresh_token|id_token|code)"\s*:\s*"[^"]+"',
        r'"\1":"***"',
        compact,
    )
    return compact[:240]


def _log_exchange_failure(provider: str, status_code: int, response_text: str, redirect_uri: str) -> None:
    normalized_uri = _normalize_redirect_uri(redirect_uri)
    logger.debug(
        "OAuth code exchange failed provider=%s status_code=%s redirect_uri_raw=%s "
        "redirect_uri_normalized=%s redirect_uri_changed=%s provider_error=%s",
        provider,
        status_code,
        _mask_redirect_uri_for_log(redirect_uri),
        _mask_redirect_uri_for_log(normalized_uri),
        normalized_uri != redirect_uri.strip(),
        _sanitize_error_snippet(response_text),
    )


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
            _log_exchange_failure("google", response.status_code, response.text, redirect_uri)
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
            _log_exchange_failure("github", response.status_code, response.text, redirect_uri)
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
    """Discord OAuth implementation with PKCE support.

    Note: Discord supports PKCE but doesn't officially document it.
    YESOD Auth implements PKCE for enhanced security.
    """

    AUTHORIZE_URL = "https://discord.com/api/oauth2/authorize"
    TOKEN_URL = "https://discord.com/api/oauth2/token"
    USERINFO_URL = "https://discord.com/api/users/@me"

    @classmethod
    def get_authorize_url(
        cls,
        redirect_uri: str,
        state: str,
        code_challenge: str | None = None,
    ) -> str:
        """Get the Discord OAuth authorization URL with optional PKCE."""
        params = {
            "client_id": settings.DISCORD_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "identify email",
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
        """Exchange authorization code for tokens with optional PKCE verifier."""
        data = {
            "client_id": settings.DISCORD_CLIENT_ID,
            "client_secret": settings.DISCORD_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        }
        if code_verifier:
            data["code_verifier"] = code_verifier
        async with httpx.AsyncClient() as client:
            response = await client.post(
                cls.TOKEN_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if response.status_code == 200:
                return response.json()
            _log_exchange_failure("discord", response.status_code, response.text, redirect_uri)
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
            _log_exchange_failure("x", response.status_code, response.text, redirect_uri)
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


class LinkedInOAuth:
    """LinkedIn OAuth 2.0 implementation with OpenID Connect."""

    AUTHORIZE_URL = "https://www.linkedin.com/oauth/v2/authorization"
    TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
    USERINFO_URL = "https://api.linkedin.com/v2/userinfo"

    @classmethod
    def get_authorize_url(
        cls,
        redirect_uri: str,
        state: str,
        code_challenge: str | None = None,
    ) -> str:
        """Get the LinkedIn OAuth authorization URL with optional PKCE."""
        params = {
            "client_id": settings.LINKEDIN_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid profile email",
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
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": settings.LINKEDIN_CLIENT_ID,
            "client_secret": settings.LINKEDIN_CLIENT_SECRET,
        }
        if code_verifier:
            data["code_verifier"] = code_verifier

        async with httpx.AsyncClient() as client:
            response = await client.post(
                cls.TOKEN_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if response.status_code == 200:
                return response.json()
            _log_exchange_failure("linkedin", response.status_code, response.text, redirect_uri)
            return None

    @classmethod
    async def get_user_info(cls, access_token: str) -> dict | None:
        """Get user info from LinkedIn using OpenID Connect userinfo endpoint."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                cls.USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if response.status_code == 200:
                return response.json()
            return None


class FacebookOAuth:
    """Facebook OAuth 2.0 implementation."""

    AUTHORIZE_URL = "https://www.facebook.com/v18.0/dialog/oauth"
    TOKEN_URL = "https://graph.facebook.com/v18.0/oauth/access_token"
    USERINFO_URL = "https://graph.facebook.com/v18.0/me"

    @classmethod
    def get_authorize_url(
        cls,
        redirect_uri: str,
        state: str,
        code_challenge: str | None = None,
    ) -> str:
        """Get the Facebook OAuth authorization URL with optional PKCE."""
        params = {
            "client_id": settings.FACEBOOK_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "email public_profile",
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
        params = {
            "client_id": settings.FACEBOOK_CLIENT_ID,
            "client_secret": settings.FACEBOOK_CLIENT_SECRET,
            "code": code,
            "redirect_uri": redirect_uri,
        }
        if code_verifier:
            params["code_verifier"] = code_verifier

        async with httpx.AsyncClient() as client:
            response = await client.get(cls.TOKEN_URL, params=params)
            if response.status_code == 200:
                return response.json()
            _log_exchange_failure("facebook", response.status_code, response.text, redirect_uri)
            return None

    @classmethod
    async def get_user_info(cls, access_token: str) -> dict | None:
        """Get user info from Facebook."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                cls.USERINFO_URL,
                params={
                    "fields": "id,name,email,picture.type(large)",
                    "access_token": access_token,
                },
            )
            if response.status_code == 200:
                data = response.json()
                # Extract picture URL from nested structure
                if data.get("picture", {}).get("data", {}).get("url"):
                    data["picture_url"] = data["picture"]["data"]["url"]
                return data
            return None


class SlackOAuth:
    """Slack OAuth 2.0 implementation with OpenID Connect and PKCE support.

    Note: Slack does not officially document PKCE support.
    YESOD Auth implements PKCE for enhanced security (yesod-auth custom implementation).
    """

    AUTHORIZE_URL = "https://slack.com/openid/connect/authorize"
    TOKEN_URL = "https://slack.com/api/openid.connect.token"
    USERINFO_URL = "https://slack.com/api/openid.connect.userInfo"

    @classmethod
    def get_authorize_url(
        cls,
        redirect_uri: str,
        state: str,
        code_challenge: str | None = None,
        nonce: str | None = None,
    ) -> str:
        """Get the Slack OAuth authorization URL with optional PKCE."""
        params = {
            "client_id": settings.SLACK_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
        }
        if code_challenge:
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = "S256"
        if nonce:
            params["nonce"] = nonce
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{cls.AUTHORIZE_URL}?{query}"

    @classmethod
    async def exchange_code(
        cls,
        code: str,
        redirect_uri: str,
        code_verifier: str | None = None,
    ) -> dict | None:
        """Exchange authorization code for tokens with optional PKCE verifier."""
        data = {
            "client_id": settings.SLACK_CLIENT_ID,
            "client_secret": settings.SLACK_CLIENT_SECRET,
            "code": code,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
        if code_verifier:
            data["code_verifier"] = code_verifier
        async with httpx.AsyncClient() as client:
            response = await client.post(
                cls.TOKEN_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if response.status_code == 200:
                resp_data = response.json()
                if resp_data.get("ok"):
                    return resp_data
            _log_exchange_failure("slack", response.status_code, response.text, redirect_uri)
            return None

    @classmethod
    async def get_user_info(cls, access_token: str) -> dict | None:
        """Get user info from Slack using OpenID Connect userinfo endpoint."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                cls.USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    return data
            return None


class TwitchOAuth:
    """Twitch OAuth 2.0 implementation with OpenID Connect and PKCE support.

    Note: Twitch does not officially document PKCE support.
    YESOD Auth implements PKCE for enhanced security (yesod-auth custom implementation).
    """

    AUTHORIZE_URL = "https://id.twitch.tv/oauth2/authorize"
    TOKEN_URL = "https://id.twitch.tv/oauth2/token"
    USERINFO_URL = "https://api.twitch.tv/helix/users"

    @classmethod
    def get_authorize_url(
        cls,
        redirect_uri: str,
        state: str,
        code_challenge: str | None = None,
        nonce: str | None = None,
    ) -> str:
        """Get the Twitch OAuth authorization URL with optional PKCE."""
        params = {
            "client_id": settings.TWITCH_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid user:read:email",
            "state": state,
        }
        if code_challenge:
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = "S256"
        if nonce:
            params["nonce"] = nonce
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{cls.AUTHORIZE_URL}?{query}"

    @classmethod
    async def exchange_code(
        cls,
        code: str,
        redirect_uri: str,
        code_verifier: str | None = None,
    ) -> dict | None:
        """Exchange authorization code for tokens with optional PKCE verifier."""
        data = {
            "client_id": settings.TWITCH_CLIENT_ID,
            "client_secret": settings.TWITCH_CLIENT_SECRET,
            "code": code,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
        if code_verifier:
            data["code_verifier"] = code_verifier
        async with httpx.AsyncClient() as client:
            response = await client.post(
                cls.TOKEN_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if response.status_code == 200:
                return response.json()
            _log_exchange_failure("twitch", response.status_code, response.text, redirect_uri)
            return None

    @classmethod
    async def get_user_info(cls, access_token: str) -> dict | None:
        """Get user info from Twitch Helix API."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                cls.USERINFO_URL,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Client-Id": settings.TWITCH_CLIENT_ID,
                },
            )
            if response.status_code == 200:
                data = response.json()
                # Twitch API wraps user data in "data" array
                users = data.get("data", [])
                if users:
                    return users[0]
            return None
