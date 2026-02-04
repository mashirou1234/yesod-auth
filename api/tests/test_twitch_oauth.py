"""Tests for Twitch OAuth implementation."""

from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from app.auth.mock_oauth import MockOAuthUser, get_mock_user
from app.auth.oauth import TwitchOAuth


class TestTwitchOAuthAuthorizeUrl:
    """Tests for Twitch OAuth authorization URL generation."""

    def test_authorize_url_contains_required_params(self):
        """Test that authorize URL contains all required parameters."""
        with patch("app.auth.oauth.settings") as mock_settings:
            mock_settings.TWITCH_CLIENT_ID = "test-client-id"

            url = TwitchOAuth.get_authorize_url(
                redirect_uri="http://localhost:8000/callback",
                state="test-state-123",
            )

            parsed = urlparse(url)
            params = parse_qs(parsed.query)

            assert parsed.scheme == "https"
            assert parsed.netloc == "id.twitch.tv"
            assert parsed.path == "/oauth2/authorize"
            assert params["client_id"] == ["test-client-id"]
            assert params["redirect_uri"] == ["http://localhost:8000/callback"]
            assert params["state"] == ["test-state-123"]
            assert params["response_type"] == ["code"]
            assert "openid" in params["scope"][0]
            assert "user:read:email" in params["scope"][0]

    def test_authorize_url_with_nonce(self):
        """Test that nonce parameter is included when provided."""
        with patch("app.auth.oauth.settings") as mock_settings:
            mock_settings.TWITCH_CLIENT_ID = "test-client-id"

            url = TwitchOAuth.get_authorize_url(
                redirect_uri="http://localhost:8000/callback",
                state="test-state-123",
                nonce="test-nonce-abc",
            )

            parsed = urlparse(url)
            params = parse_qs(parsed.query)

            assert params["nonce"] == ["test-nonce-abc"]

    def test_authorize_url_without_nonce(self):
        """Test that nonce parameter is not included when not provided."""
        with patch("app.auth.oauth.settings") as mock_settings:
            mock_settings.TWITCH_CLIENT_ID = "test-client-id"

            url = TwitchOAuth.get_authorize_url(
                redirect_uri="http://localhost:8000/callback",
                state="test-state-123",
            )

            parsed = urlparse(url)
            params = parse_qs(parsed.query)

            assert "nonce" not in params


class TestTwitchOAuthExchangeCode:
    """Tests for Twitch OAuth code exchange."""

    @pytest.mark.asyncio
    async def test_exchange_code_success(self, respx_mock):
        """Test successful code exchange."""
        respx_mock.post("https://id.twitch.tv/oauth2/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "test_access_token",
                    "token_type": "bearer",
                    "expires_in": 14400,
                    "refresh_token": "test_refresh_token",
                    "scope": ["openid", "user:read:email"],
                },
            )
        )

        with patch("app.auth.oauth.settings") as mock_settings:
            mock_settings.TWITCH_CLIENT_ID = "test-client-id"
            mock_settings.TWITCH_CLIENT_SECRET = "test-client-secret"

            result = await TwitchOAuth.exchange_code(
                code="test-code",
                redirect_uri="http://localhost:8000/callback",
            )

            assert result is not None
            assert result["access_token"] == "test_access_token"

    @pytest.mark.asyncio
    async def test_exchange_code_failure(self, respx_mock):
        """Test code exchange failure."""
        respx_mock.post("https://id.twitch.tv/oauth2/token").mock(return_value=httpx.Response(400))

        with patch("app.auth.oauth.settings") as mock_settings:
            mock_settings.TWITCH_CLIENT_ID = "test-client-id"
            mock_settings.TWITCH_CLIENT_SECRET = "test-client-secret"

            result = await TwitchOAuth.exchange_code(
                code="invalid-code",
                redirect_uri="http://localhost:8000/callback",
            )

            assert result is None


class TestTwitchOAuthUserInfo:
    """Tests for Twitch OAuth user info retrieval."""

    @pytest.mark.asyncio
    async def test_get_user_info_success(self, respx_mock):
        """Test getting user info successfully."""
        respx_mock.get("https://api.twitch.tv/helix/users").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "123456789",
                            "login": "johndoe",
                            "display_name": "JohnDoe",
                            "email": "john@example.com",
                            "profile_image_url": "https://example.com/avatar.jpg",
                            "broadcaster_type": "",
                            "description": "Test user",
                            "type": "",
                        }
                    ]
                },
            )
        )

        with patch("app.auth.oauth.settings") as mock_settings:
            mock_settings.TWITCH_CLIENT_ID = "test-client-id"

            result = await TwitchOAuth.get_user_info("test-token")

            assert result is not None
            assert result["id"] == "123456789"
            assert result["login"] == "johndoe"
            assert result["display_name"] == "JohnDoe"
            assert result["email"] == "john@example.com"

    @pytest.mark.asyncio
    async def test_get_user_info_empty_data(self, respx_mock):
        """Test user info retrieval with empty data array."""
        respx_mock.get("https://api.twitch.tv/helix/users").mock(
            return_value=httpx.Response(200, json={"data": []})
        )

        with patch("app.auth.oauth.settings") as mock_settings:
            mock_settings.TWITCH_CLIENT_ID = "test-client-id"

            result = await TwitchOAuth.get_user_info("test-token")

            assert result is None

    @pytest.mark.asyncio
    async def test_get_user_info_failure(self, respx_mock):
        """Test user info retrieval failure."""
        respx_mock.get("https://api.twitch.tv/helix/users").mock(return_value=httpx.Response(401))

        with patch("app.auth.oauth.settings") as mock_settings:
            mock_settings.TWITCH_CLIENT_ID = "test-client-id"

            result = await TwitchOAuth.get_user_info("invalid-token")

            assert result is None


class TestMockOAuthTwitchFormat:
    """Tests for MockOAuthUser Twitch format conversion."""

    def test_to_twitch_format_contains_required_fields(self):
        """Test that Twitch format contains all required fields."""
        mock_user = get_mock_user("alice")
        twitch_format = mock_user.to_twitch_format()

        assert "id" in twitch_format
        assert "login" in twitch_format
        assert "display_name" in twitch_format
        assert "email" in twitch_format
        assert "profile_image_url" in twitch_format

    def test_to_twitch_format_login_is_lowercase(self):
        """Test that Twitch format login is lowercase with underscores."""
        mock_user = MockOAuthUser(
            id="test-123",
            email="test@example.com",
            name="Test User",
            picture="https://example.com/avatar.png",
        )
        twitch_format = mock_user.to_twitch_format()

        assert twitch_format["login"] == "test_user"
        assert twitch_format["display_name"] == "Test User"


class TestTwitchMockLogin:
    """Tests for Twitch mock login endpoint."""

    @pytest.mark.asyncio
    async def test_mock_login_twitch_provider(self, client):
        """Test mock login with Twitch provider."""
        response = await client.get("/api/v1/auth/mock/login?user=alice&provider=twitch")

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["provider"] == "twitch"
        assert data["mock_user"] == "alice"

    @pytest.mark.asyncio
    async def test_mock_login_twitch_creates_user(self, client):
        """Test that mock login creates user in database."""
        response = await client.get("/api/v1/auth/mock/login?user=bob&provider=twitch")

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "bob@example.com"
