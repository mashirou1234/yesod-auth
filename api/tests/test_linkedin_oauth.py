"""Tests for LinkedIn OAuth implementation."""

from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from app.auth.mock_oauth import MockOAuthUser, get_mock_user
from app.auth.oauth import LinkedInOAuth


class TestLinkedInOAuthAuthorizeUrl:
    """Tests for LinkedIn OAuth authorization URL generation."""

    def test_authorize_url_contains_required_params(self):
        """Test that authorize URL contains all required parameters."""
        with patch("app.auth.oauth.settings") as mock_settings:
            mock_settings.LINKEDIN_CLIENT_ID = "test-client-id"

            url = LinkedInOAuth.get_authorize_url(
                redirect_uri="http://localhost:8000/callback",
                state="test-state-123",
            )

            parsed = urlparse(url)
            params = parse_qs(parsed.query)

            assert parsed.scheme == "https"
            assert parsed.netloc == "www.linkedin.com"
            assert parsed.path == "/oauth/v2/authorization"
            assert params["client_id"] == ["test-client-id"]
            assert params["redirect_uri"] == ["http://localhost:8000/callback"]
            assert params["state"] == ["test-state-123"]
            assert params["response_type"] == ["code"]
            assert "openid" in params["scope"][0]
            assert "profile" in params["scope"][0]
            assert "email" in params["scope"][0]

    def test_authorize_url_with_pkce(self):
        """Test that PKCE parameters are included when provided."""
        with patch("app.auth.oauth.settings") as mock_settings:
            mock_settings.LINKEDIN_CLIENT_ID = "test-client-id"

            url = LinkedInOAuth.get_authorize_url(
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
            mock_settings.LINKEDIN_CLIENT_ID = "test-client-id"

            url = LinkedInOAuth.get_authorize_url(
                redirect_uri="http://localhost:8000/callback",
                state="test-state-123",
            )

            parsed = urlparse(url)
            params = parse_qs(parsed.query)

            assert "code_challenge" not in params
            assert "code_challenge_method" not in params


class TestLinkedInOAuthExchangeCode:
    """Tests for LinkedIn OAuth code exchange."""

    @pytest.mark.asyncio
    async def test_exchange_code_success(self, respx_mock):
        """Test successful code exchange."""
        respx_mock.post("https://www.linkedin.com/oauth/v2/accessToken").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "test_access_token",
                    "token_type": "Bearer",
                    "expires_in": 5184000,
                    "scope": "openid profile email",
                },
            )
        )

        with patch("app.auth.oauth.settings") as mock_settings:
            mock_settings.LINKEDIN_CLIENT_ID = "test-client-id"
            mock_settings.LINKEDIN_CLIENT_SECRET = "test-client-secret"

            result = await LinkedInOAuth.exchange_code(
                code="test-code",
                redirect_uri="http://localhost:8000/callback",
            )

            assert result is not None
            assert result["access_token"] == "test_access_token"

    @pytest.mark.asyncio
    async def test_exchange_code_with_pkce(self, respx_mock):
        """Test code exchange with PKCE verifier."""
        respx_mock.post("https://www.linkedin.com/oauth/v2/accessToken").mock(
            return_value=httpx.Response(200, json={"access_token": "test_access_token"})
        )

        with patch("app.auth.oauth.settings") as mock_settings:
            mock_settings.LINKEDIN_CLIENT_ID = "test-client-id"
            mock_settings.LINKEDIN_CLIENT_SECRET = "test-client-secret"

            result = await LinkedInOAuth.exchange_code(
                code="test-code",
                redirect_uri="http://localhost:8000/callback",
                code_verifier="test-verifier",
            )

            assert result is not None

    @pytest.mark.asyncio
    async def test_exchange_code_failure(self, respx_mock):
        """Test code exchange failure."""
        respx_mock.post("https://www.linkedin.com/oauth/v2/accessToken").mock(
            return_value=httpx.Response(400)
        )

        with patch("app.auth.oauth.settings") as mock_settings:
            mock_settings.LINKEDIN_CLIENT_ID = "test-client-id"
            mock_settings.LINKEDIN_CLIENT_SECRET = "test-client-secret"

            result = await LinkedInOAuth.exchange_code(
                code="invalid-code",
                redirect_uri="http://localhost:8000/callback",
            )

            assert result is None


class TestLinkedInOAuthUserInfo:
    """Tests for LinkedIn OAuth user info retrieval."""

    @pytest.mark.asyncio
    async def test_get_user_info_success(self, respx_mock):
        """Test getting user info successfully (OpenID Connect format)."""
        respx_mock.get("https://api.linkedin.com/v2/userinfo").mock(
            return_value=httpx.Response(
                200,
                json={
                    "sub": "abc123",
                    "name": "John Doe",
                    "given_name": "John",
                    "family_name": "Doe",
                    "picture": "https://media.licdn.com/dms/image/test.jpg",
                    "email": "john@example.com",
                    "email_verified": True,
                },
            )
        )

        result = await LinkedInOAuth.get_user_info("test-token")

        assert result is not None
        assert result["sub"] == "abc123"
        assert result["name"] == "John Doe"
        assert result["email"] == "john@example.com"

    @pytest.mark.asyncio
    async def test_get_user_info_failure(self, respx_mock):
        """Test user info retrieval failure."""
        respx_mock.get("https://api.linkedin.com/v2/userinfo").mock(
            return_value=httpx.Response(401)
        )

        result = await LinkedInOAuth.get_user_info("invalid-token")

        assert result is None


class TestMockOAuthLinkedInFormat:
    """Tests for MockOAuthUser LinkedIn format conversion."""

    def test_to_linkedin_format_contains_required_fields(self):
        """Test that LinkedIn format contains all required fields (OpenID Connect)."""
        mock_user = get_mock_user("alice")
        linkedin_format = mock_user.to_linkedin_format()

        assert "sub" in linkedin_format
        assert "name" in linkedin_format
        assert "email" in linkedin_format
        assert "picture" in linkedin_format
        assert "email_verified" in linkedin_format

    def test_to_linkedin_format_uses_sub_instead_of_id(self):
        """Test that LinkedIn format uses 'sub' field (OpenID Connect standard)."""
        mock_user = MockOAuthUser(
            id="test-123",
            email="test@example.com",
            name="Test User",
            picture="https://example.com/avatar.png",
        )
        linkedin_format = mock_user.to_linkedin_format()

        assert linkedin_format["sub"] == "test-123"
        assert "id" not in linkedin_format


class TestLinkedInMockLogin:
    """Tests for LinkedIn mock login endpoint."""

    @pytest.mark.asyncio
    async def test_mock_login_linkedin_provider(self, client):
        """Test mock login with LinkedIn provider."""
        response = await client.get("/api/v1/auth/mock/login?user=alice&provider=linkedin")

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["provider"] == "linkedin"
        assert data["mock_user"] == "alice"

    @pytest.mark.asyncio
    async def test_mock_login_linkedin_creates_user(self, client):
        """Test that mock login creates user in database."""
        response = await client.get("/api/v1/auth/mock/login?user=bob&provider=linkedin")

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "bob@example.com"
