"""Tests for Discord OAuth implementation."""

from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from app.auth.mock_oauth import MockOAuthUser, get_mock_user
from app.auth.oauth import DiscordOAuth


class TestDiscordOAuthAuthorizeUrl:
    """Tests for Discord OAuth authorization URL generation."""

    def test_authorize_url_contains_required_params(self):
        """Test that authorize URL contains all required parameters."""
        with patch("app.auth.oauth.settings") as mock_settings:
            mock_settings.DISCORD_CLIENT_ID = "test-client-id"

            url = DiscordOAuth.get_authorize_url(
                redirect_uri="http://localhost:8000/callback",
                state="test-state-123",
            )

            parsed = urlparse(url)
            params = parse_qs(parsed.query)

            assert parsed.scheme == "https"
            assert parsed.netloc == "discord.com"
            assert parsed.path == "/api/oauth2/authorize"
            assert params["client_id"] == ["test-client-id"]
            assert params["redirect_uri"] == ["http://localhost:8000/callback"]
            assert params["state"] == ["test-state-123"]
            assert params["response_type"] == ["code"]
            assert "identify" in params["scope"][0]
            assert "email" in params["scope"][0]

    def test_authorize_url_with_pkce(self):
        """Test that PKCE parameters are included when provided."""
        with patch("app.auth.oauth.settings") as mock_settings:
            mock_settings.DISCORD_CLIENT_ID = "test-client-id"

            url = DiscordOAuth.get_authorize_url(
                redirect_uri="http://localhost:8000/callback",
                state="test-state-123",
                code_challenge="test-code-challenge",
            )

            parsed = urlparse(url)
            params = parse_qs(parsed.query)

            assert params["code_challenge"] == ["test-code-challenge"]
            assert params["code_challenge_method"] == ["S256"]

    def test_authorize_url_without_pkce(self):
        """Test that PKCE parameters are not included when not provided."""
        with patch("app.auth.oauth.settings") as mock_settings:
            mock_settings.DISCORD_CLIENT_ID = "test-client-id"

            url = DiscordOAuth.get_authorize_url(
                redirect_uri="http://localhost:8000/callback",
                state="test-state-123",
            )

            parsed = urlparse(url)
            params = parse_qs(parsed.query)

            assert "code_challenge" not in params
            assert "code_challenge_method" not in params


class TestDiscordOAuthExchangeCode:
    """Tests for Discord OAuth code exchange."""

    @pytest.mark.asyncio
    async def test_exchange_code_success(self, respx_mock):
        """Test successful code exchange."""
        respx_mock.post("https://discord.com/api/oauth2/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "test_access_token",
                    "token_type": "Bearer",
                    "expires_in": 604800,
                    "refresh_token": "test_refresh_token",
                    "scope": "identify email",
                },
            )
        )

        with patch("app.auth.oauth.settings") as mock_settings:
            mock_settings.DISCORD_CLIENT_ID = "test-client-id"
            mock_settings.DISCORD_CLIENT_SECRET = "test-client-secret"

            result = await DiscordOAuth.exchange_code(
                code="test-code",
                redirect_uri="http://localhost:8000/callback",
            )

            assert result is not None
            assert result["access_token"] == "test_access_token"

    @pytest.mark.asyncio
    async def test_exchange_code_with_pkce(self, respx_mock):
        """Test code exchange with PKCE verifier."""
        respx_mock.post("https://discord.com/api/oauth2/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "test_access_token",
                    "token_type": "Bearer",
                    "expires_in": 604800,
                    "refresh_token": "test_refresh_token",
                    "scope": "identify email",
                },
            )
        )

        with patch("app.auth.oauth.settings") as mock_settings:
            mock_settings.DISCORD_CLIENT_ID = "test-client-id"
            mock_settings.DISCORD_CLIENT_SECRET = "test-client-secret"

            result = await DiscordOAuth.exchange_code(
                code="test-code",
                redirect_uri="http://localhost:8000/callback",
                code_verifier="test-code-verifier",
            )

            assert result is not None
            assert result["access_token"] == "test_access_token"

    @pytest.mark.asyncio
    async def test_exchange_code_failure(self, respx_mock):
        """Test code exchange failure."""
        respx_mock.post("https://discord.com/api/oauth2/token").mock(
            return_value=httpx.Response(400)
        )

        with patch("app.auth.oauth.settings") as mock_settings:
            mock_settings.DISCORD_CLIENT_ID = "test-client-id"
            mock_settings.DISCORD_CLIENT_SECRET = "test-client-secret"

            result = await DiscordOAuth.exchange_code(
                code="invalid-code",
                redirect_uri="http://localhost:8000/callback",
            )

            assert result is None


class TestDiscordOAuthUserInfo:
    """Tests for Discord OAuth user info retrieval."""

    @pytest.mark.asyncio
    async def test_get_user_info_success(self, respx_mock):
        """Test getting user info successfully."""
        respx_mock.get("https://discord.com/api/users/@me").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "123456789012345678",
                    "username": "johndoe",
                    "discriminator": "1234",
                    "email": "john@example.com",
                    "avatar": "abc123",
                    "verified": True,
                },
            )
        )

        result = await DiscordOAuth.get_user_info("test-token")

        assert result is not None
        assert result["id"] == "123456789012345678"
        assert result["username"] == "johndoe"
        assert result["email"] == "john@example.com"
        assert "avatar_url" in result

    @pytest.mark.asyncio
    async def test_get_user_info_without_avatar(self, respx_mock):
        """Test getting user info without avatar."""
        respx_mock.get("https://discord.com/api/users/@me").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "123456789012345678",
                    "username": "johndoe",
                    "discriminator": "1234",
                    "email": "john@example.com",
                    "avatar": None,
                    "verified": True,
                },
            )
        )

        result = await DiscordOAuth.get_user_info("test-token")

        assert result is not None
        assert "avatar_url" not in result

    @pytest.mark.asyncio
    async def test_get_user_info_failure(self, respx_mock):
        """Test user info retrieval failure."""
        respx_mock.get("https://discord.com/api/users/@me").mock(return_value=httpx.Response(401))

        result = await DiscordOAuth.get_user_info("invalid-token")

        assert result is None


class TestMockOAuthDiscordFormat:
    """Tests for MockOAuthUser Discord format conversion."""

    def test_to_discord_format_contains_required_fields(self):
        """Test that Discord format contains all required fields."""
        mock_user = get_mock_user("alice")
        discord_format = mock_user.to_discord_format()

        assert "id" in discord_format
        assert "username" in discord_format
        assert "email" in discord_format
        assert "avatar" in discord_format

    def test_to_discord_format_username_matches_name(self):
        """Test that Discord format username matches the user's name."""
        mock_user = MockOAuthUser(
            id="test-123",
            email="test@example.com",
            name="Test User",
            picture="https://example.com/avatar.png",
        )
        discord_format = mock_user.to_discord_format()

        assert discord_format["username"] == "Test User"


class TestDiscordMockLogin:
    """Tests for Discord mock login endpoint."""

    @pytest.mark.asyncio
    async def test_mock_login_discord_provider(self, client):
        """Test mock login with Discord provider."""
        response = await client.get("/api/v1/auth/mock/login?user=alice&provider=discord")

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["provider"] == "discord"
        assert data["mock_user"] == "alice"

    @pytest.mark.asyncio
    async def test_mock_login_discord_creates_user(self, client):
        """Test that mock login creates user in database."""
        response = await client.get("/api/v1/auth/mock/login?user=bob&provider=discord")

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "bob@example.com"
