"""Tests for Facebook OAuth implementation."""

from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from app.auth.mock_oauth import MockOAuthUser, get_mock_user
from app.auth.oauth import FacebookOAuth


class TestFacebookOAuthAuthorizeUrl:
    """Tests for Facebook OAuth authorization URL generation."""

    def test_authorize_url_contains_required_params(self):
        """Test that authorize URL contains all required parameters."""
        with patch("app.auth.oauth.settings") as mock_settings:
            mock_settings.FACEBOOK_CLIENT_ID = "test-client-id"

            url = FacebookOAuth.get_authorize_url(
                redirect_uri="http://localhost:8000/callback",
                state="test-state-123",
            )

            parsed = urlparse(url)
            params = parse_qs(parsed.query)

            assert parsed.scheme == "https"
            assert parsed.netloc == "www.facebook.com"
            assert parsed.path == "/v18.0/dialog/oauth"
            assert params["client_id"] == ["test-client-id"]
            assert params["redirect_uri"] == ["http://localhost:8000/callback"]
            assert params["state"] == ["test-state-123"]
            assert params["response_type"] == ["code"]
            assert "email" in params["scope"][0]
            assert "public_profile" in params["scope"][0]

    def test_authorize_url_with_pkce(self):
        """Test that PKCE parameters are included when provided."""
        with patch("app.auth.oauth.settings") as mock_settings:
            mock_settings.FACEBOOK_CLIENT_ID = "test-client-id"

            url = FacebookOAuth.get_authorize_url(
                redirect_uri="http://localhost:8000/callback",
                state="test-state-123",
                code_challenge="test-challenge-abc",
            )

            parsed = urlparse(url)
            params = parse_qs(parsed.query)

            assert params["code_challenge"] == ["test-challenge-abc"]
            assert params["code_challenge_method"] == ["S256"]

    def test_authorize_url_without_pkce(self):
        """Test that PKCE parameters are not included when not provided."""
        with patch("app.auth.oauth.settings") as mock_settings:
            mock_settings.FACEBOOK_CLIENT_ID = "test-client-id"

            url = FacebookOAuth.get_authorize_url(
                redirect_uri="http://localhost:8000/callback",
                state="test-state-123",
            )

            parsed = urlparse(url)
            params = parse_qs(parsed.query)

            assert "code_challenge" not in params
            assert "code_challenge_method" not in params


class TestFacebookOAuthExchangeCode:
    """Tests for Facebook OAuth code exchange."""

    @pytest.mark.asyncio
    async def test_exchange_code_success(self, respx_mock):
        """Test successful code exchange."""
        respx_mock.get("https://graph.facebook.com/v18.0/oauth/access_token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "test_access_token",
                    "token_type": "bearer",
                    "expires_in": 5184000,
                },
            )
        )

        with patch("app.auth.oauth.settings") as mock_settings:
            mock_settings.FACEBOOK_CLIENT_ID = "test-client-id"
            mock_settings.FACEBOOK_CLIENT_SECRET = "test-client-secret"

            result = await FacebookOAuth.exchange_code(
                code="test-code",
                redirect_uri="http://localhost:8000/callback",
            )

            assert result is not None
            assert result["access_token"] == "test_access_token"

    @pytest.mark.asyncio
    async def test_exchange_code_with_pkce(self, respx_mock):
        """Test code exchange with PKCE verifier."""
        respx_mock.get("https://graph.facebook.com/v18.0/oauth/access_token").mock(
            return_value=httpx.Response(200, json={"access_token": "test_access_token"})
        )

        with patch("app.auth.oauth.settings") as mock_settings:
            mock_settings.FACEBOOK_CLIENT_ID = "test-client-id"
            mock_settings.FACEBOOK_CLIENT_SECRET = "test-client-secret"

            result = await FacebookOAuth.exchange_code(
                code="test-code",
                redirect_uri="http://localhost:8000/callback",
                code_verifier="test-verifier",
            )

            assert result is not None

    @pytest.mark.asyncio
    async def test_exchange_code_failure(self, respx_mock):
        """Test code exchange failure."""
        respx_mock.get("https://graph.facebook.com/v18.0/oauth/access_token").mock(
            return_value=httpx.Response(400)
        )

        with patch("app.auth.oauth.settings") as mock_settings:
            mock_settings.FACEBOOK_CLIENT_ID = "test-client-id"
            mock_settings.FACEBOOK_CLIENT_SECRET = "test-client-secret"

            result = await FacebookOAuth.exchange_code(
                code="invalid-code",
                redirect_uri="http://localhost:8000/callback",
            )

            assert result is None


class TestFacebookOAuthUserInfo:
    """Tests for Facebook OAuth user info retrieval."""

    @pytest.mark.asyncio
    async def test_get_user_info_success(self, respx_mock):
        """Test getting user info successfully."""
        respx_mock.get("https://graph.facebook.com/v18.0/me").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "123456789",
                    "name": "John Doe",
                    "email": "john@example.com",
                    "picture": {
                        "data": {
                            "url": "https://example.com/avatar.jpg",
                            "is_silhouette": False,
                        }
                    },
                },
            )
        )

        result = await FacebookOAuth.get_user_info("test-token")

        assert result is not None
        assert result["id"] == "123456789"
        assert result["name"] == "John Doe"
        assert result["email"] == "john@example.com"
        assert result["picture"]["data"]["url"] == "https://example.com/avatar.jpg"

    @pytest.mark.asyncio
    async def test_get_user_info_failure(self, respx_mock):
        """Test user info retrieval failure."""
        respx_mock.get("https://graph.facebook.com/v18.0/me").mock(return_value=httpx.Response(401))

        result = await FacebookOAuth.get_user_info("invalid-token")

        assert result is None


class TestMockOAuthFacebookFormat:
    """Tests for MockOAuthUser Facebook format conversion."""

    def test_to_facebook_format_contains_required_fields(self):
        """Test that Facebook format contains all required fields."""
        mock_user = get_mock_user("alice")
        facebook_format = mock_user.to_facebook_format()

        assert "id" in facebook_format
        assert "name" in facebook_format
        assert "email" in facebook_format
        assert "picture" in facebook_format
        assert "data" in facebook_format["picture"]
        assert "url" in facebook_format["picture"]["data"]

    def test_to_facebook_format_picture_structure(self):
        """Test that Facebook format has correct picture structure."""
        mock_user = MockOAuthUser(
            id="test-123",
            email="test@example.com",
            name="Test User",
            picture="https://example.com/avatar.png",
        )
        facebook_format = mock_user.to_facebook_format()

        assert facebook_format["picture"]["data"]["url"] == "https://example.com/avatar.png"
        assert facebook_format["picture"]["data"]["is_silhouette"] is False


class TestFacebookMockLogin:
    """Tests for Facebook mock login endpoint."""

    @pytest.mark.asyncio
    async def test_mock_login_facebook_provider(self, client):
        """Test mock login with Facebook provider."""
        response = await client.get("/api/v1/auth/mock/login?user=alice&provider=facebook")

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["provider"] == "facebook"
        assert data["mock_user"] == "alice"

    @pytest.mark.asyncio
    async def test_mock_login_facebook_creates_user(self, client):
        """Test that mock login creates user in database."""
        response = await client.get("/api/v1/auth/mock/login?user=bob&provider=facebook")

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "bob@example.com"
