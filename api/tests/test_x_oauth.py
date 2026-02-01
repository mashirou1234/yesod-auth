"""Tests for X (Twitter) OAuth implementation."""

from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from app.auth.mock_oauth import MockOAuthUser, get_mock_user
from app.auth.oauth import XOAuth


class TestXOAuthAuthorizeUrl:
    """Tests for X OAuth authorization URL generation."""

    def test_authorize_url_contains_required_params(self):
        """Test that authorize URL contains all required parameters."""
        with patch("app.auth.oauth.settings") as mock_settings:
            mock_settings.X_CLIENT_ID = "test-client-id"

            url = XOAuth.get_authorize_url(
                redirect_uri="http://localhost:8000/callback",
                state="test-state-123",
                code_challenge="test-challenge-abc",
            )

            parsed = urlparse(url)
            params = parse_qs(parsed.query)

            assert parsed.scheme == "https"
            assert parsed.netloc == "twitter.com"
            assert parsed.path == "/i/oauth2/authorize"
            assert params["client_id"] == ["test-client-id"]
            assert params["redirect_uri"] == ["http://localhost:8000/callback"]
            assert params["state"] == ["test-state-123"]
            assert params["response_type"] == ["code"]
            assert "users.read" in params["scope"][0]
            assert "tweet.read" in params["scope"][0]

    def test_authorize_url_includes_pkce(self):
        """Test that PKCE parameters are always included (required for X)."""
        with patch("app.auth.oauth.settings") as mock_settings:
            mock_settings.X_CLIENT_ID = "test-client-id"

            url = XOAuth.get_authorize_url(
                redirect_uri="http://localhost:8000/callback",
                state="test-state-123",
                code_challenge="test-challenge-abc",
            )

            parsed = urlparse(url)
            params = parse_qs(parsed.query)

            assert params["code_challenge"] == ["test-challenge-abc"]
            assert params["code_challenge_method"] == ["S256"]


class TestXOAuthExchangeCode:
    """Tests for X OAuth code exchange."""

    @pytest.mark.asyncio
    async def test_exchange_code_success(self, respx_mock):
        """Test successful code exchange."""
        respx_mock.post("https://api.twitter.com/2/oauth2/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "test_access_token",
                    "token_type": "bearer",
                    "expires_in": 7200,
                    "scope": "users.read tweet.read",
                    "refresh_token": "test_refresh_token",
                },
            )
        )

        with patch("app.auth.oauth.settings") as mock_settings:
            mock_settings.X_CLIENT_ID = "test-client-id"
            mock_settings.X_CLIENT_SECRET = "test-client-secret"

            result = await XOAuth.exchange_code(
                code="test-code",
                redirect_uri="http://localhost:8000/callback",
                code_verifier="test-verifier",
            )

            assert result is not None
            assert result["access_token"] == "test_access_token"
            assert result["refresh_token"] == "test_refresh_token"

    @pytest.mark.asyncio
    async def test_exchange_code_failure(self, respx_mock):
        """Test code exchange failure."""
        respx_mock.post("https://api.twitter.com/2/oauth2/token").mock(
            return_value=httpx.Response(400)
        )

        with patch("app.auth.oauth.settings") as mock_settings:
            mock_settings.X_CLIENT_ID = "test-client-id"
            mock_settings.X_CLIENT_SECRET = "test-client-secret"

            result = await XOAuth.exchange_code(
                code="invalid-code",
                redirect_uri="http://localhost:8000/callback",
                code_verifier="test-verifier",
            )

            assert result is None


class TestXOAuthUserInfo:
    """Tests for X OAuth user info retrieval."""

    @pytest.mark.asyncio
    async def test_get_user_info_success(self, respx_mock):
        """Test getting user info successfully."""
        respx_mock.get("https://api.twitter.com/2/users/me").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": {
                        "id": "123456789",
                        "username": "testuser",
                        "name": "Test User",
                        "profile_image_url": "https://pbs.twimg.com/profile_images/test.jpg",
                    }
                },
            )
        )

        result = await XOAuth.get_user_info("test-token")

        assert result is not None
        assert result["id"] == "123456789"
        assert result["username"] == "testuser"
        assert result["name"] == "Test User"

    @pytest.mark.asyncio
    async def test_get_user_info_failure(self, respx_mock):
        """Test user info retrieval failure."""
        respx_mock.get("https://api.twitter.com/2/users/me").mock(return_value=httpx.Response(401))

        result = await XOAuth.get_user_info("invalid-token")

        assert result is None


class TestMockOAuthXFormat:
    """Tests for MockOAuthUser X format conversion."""

    def test_to_x_format_contains_required_fields(self):
        """Test that X format contains all required fields."""
        mock_user = get_mock_user("alice")
        x_format = mock_user.to_x_format()

        assert "id" in x_format
        assert "username" in x_format
        assert "name" in x_format
        assert "profile_image_url" in x_format
        assert "email" in x_format

    def test_to_x_format_generates_placeholder_email(self):
        """Test that X format generates placeholder email."""
        mock_user = get_mock_user("alice")
        x_format = mock_user.to_x_format()

        assert x_format["email"].endswith("@x.yesod-auth.local")

    def test_to_x_format_username_is_lowercase_with_underscores(self):
        """Test that X format username is lowercase with underscores."""
        mock_user = MockOAuthUser(
            id="test-123",
            email="test@example.com",
            name="Test User",
            picture="https://example.com/avatar.png",
        )
        x_format = mock_user.to_x_format()

        assert x_format["username"] == "test_user"
        assert " " not in x_format["username"]


class TestXMockLogin:
    """Tests for X mock login endpoint."""

    @pytest.mark.asyncio
    async def test_mock_login_x_provider(self, client):
        """Test mock login with X provider."""
        response = await client.get("/api/v1/auth/mock/login?user=alice&provider=x")

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["provider"] == "x"
        assert data["mock_user"] == "alice"

    @pytest.mark.asyncio
    async def test_mock_login_x_creates_user_with_placeholder_email(self, client):
        """Test that mock login creates user with placeholder email."""
        response = await client.get("/api/v1/auth/mock/login?user=bob&provider=x")

        assert response.status_code == 200
        data = response.json()
        # X uses placeholder email since it doesn't provide real email
        assert "@x.yesod-auth.local" in data["email"]
