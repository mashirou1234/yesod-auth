"""Tests for Slack OAuth implementation."""

from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from app.auth.mock_oauth import MockOAuthUser, get_mock_user
from app.auth.oauth import SlackOAuth


class TestSlackOAuthAuthorizeUrl:
    """Tests for Slack OAuth authorization URL generation."""

    def test_authorize_url_contains_required_params(self):
        """Test that authorize URL contains all required parameters."""
        with patch("app.auth.oauth.settings") as mock_settings:
            mock_settings.SLACK_CLIENT_ID = "test-client-id"

            url = SlackOAuth.get_authorize_url(
                redirect_uri="http://localhost:8000/callback",
                state="test-state-123",
            )

            parsed = urlparse(url)
            params = parse_qs(parsed.query)

            assert parsed.scheme == "https"
            assert parsed.netloc == "slack.com"
            assert parsed.path == "/openid/connect/authorize"
            assert params["client_id"] == ["test-client-id"]
            assert params["redirect_uri"] == ["http://localhost:8000/callback"]
            assert params["state"] == ["test-state-123"]
            assert params["response_type"] == ["code"]
            assert "openid" in params["scope"][0]
            assert "email" in params["scope"][0]
            assert "profile" in params["scope"][0]

    def test_authorize_url_with_nonce(self):
        """Test that nonce parameter is included when provided."""
        with patch("app.auth.oauth.settings") as mock_settings:
            mock_settings.SLACK_CLIENT_ID = "test-client-id"

            url = SlackOAuth.get_authorize_url(
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
            mock_settings.SLACK_CLIENT_ID = "test-client-id"

            url = SlackOAuth.get_authorize_url(
                redirect_uri="http://localhost:8000/callback",
                state="test-state-123",
            )

            parsed = urlparse(url)
            params = parse_qs(parsed.query)

            assert "nonce" not in params

    def test_authorize_url_with_pkce(self):
        """Test that PKCE parameters are included when provided."""
        with patch("app.auth.oauth.settings") as mock_settings:
            mock_settings.SLACK_CLIENT_ID = "test-client-id"

            url = SlackOAuth.get_authorize_url(
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
            mock_settings.SLACK_CLIENT_ID = "test-client-id"

            url = SlackOAuth.get_authorize_url(
                redirect_uri="http://localhost:8000/callback",
                state="test-state-123",
            )

            parsed = urlparse(url)
            params = parse_qs(parsed.query)

            assert "code_challenge" not in params
            assert "code_challenge_method" not in params


class TestSlackOAuthExchangeCode:
    """Tests for Slack OAuth code exchange."""

    @pytest.mark.asyncio
    async def test_exchange_code_success(self, respx_mock):
        """Test successful code exchange."""
        respx_mock.post("https://slack.com/api/openid.connect.token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "ok": True,
                    "access_token": "test_access_token",
                    "token_type": "Bearer",
                    "id_token": "test_id_token",
                },
            )
        )

        with patch("app.auth.oauth.settings") as mock_settings:
            mock_settings.SLACK_CLIENT_ID = "test-client-id"
            mock_settings.SLACK_CLIENT_SECRET = "test-client-secret"

            result = await SlackOAuth.exchange_code(
                code="test-code",
                redirect_uri="http://localhost:8000/callback",
            )

            assert result is not None
            assert result["access_token"] == "test_access_token"
            assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_exchange_code_failure_not_ok(self, respx_mock):
        """Test code exchange failure when ok is false."""
        respx_mock.post("https://slack.com/api/openid.connect.token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "ok": False,
                    "error": "invalid_code",
                },
            )
        )

        with patch("app.auth.oauth.settings") as mock_settings:
            mock_settings.SLACK_CLIENT_ID = "test-client-id"
            mock_settings.SLACK_CLIENT_SECRET = "test-client-secret"

            result = await SlackOAuth.exchange_code(
                code="invalid-code",
                redirect_uri="http://localhost:8000/callback",
            )

            assert result is None

    @pytest.mark.asyncio
    async def test_exchange_code_failure_http_error(self, respx_mock):
        """Test code exchange failure on HTTP error."""
        respx_mock.post("https://slack.com/api/openid.connect.token").mock(
            return_value=httpx.Response(400)
        )

        with patch("app.auth.oauth.settings") as mock_settings:
            mock_settings.SLACK_CLIENT_ID = "test-client-id"
            mock_settings.SLACK_CLIENT_SECRET = "test-client-secret"

            result = await SlackOAuth.exchange_code(
                code="invalid-code",
                redirect_uri="http://localhost:8000/callback",
            )

            assert result is None

    @pytest.mark.asyncio
    async def test_exchange_code_with_pkce(self, respx_mock):
        """Test code exchange with PKCE verifier."""
        respx_mock.post("https://slack.com/api/openid.connect.token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "ok": True,
                    "access_token": "test_access_token",
                    "token_type": "Bearer",
                    "id_token": "test_id_token",
                },
            )
        )

        with patch("app.auth.oauth.settings") as mock_settings:
            mock_settings.SLACK_CLIENT_ID = "test-client-id"
            mock_settings.SLACK_CLIENT_SECRET = "test-client-secret"

            result = await SlackOAuth.exchange_code(
                code="test-code",
                redirect_uri="http://localhost:8000/callback",
                code_verifier="test-code-verifier",
            )

            assert result is not None
            assert result["access_token"] == "test_access_token"


class TestSlackOAuthUserInfo:
    """Tests for Slack OAuth user info retrieval."""

    @pytest.mark.asyncio
    async def test_get_user_info_success(self, respx_mock):
        """Test getting user info successfully (OpenID Connect format)."""
        respx_mock.get("https://slack.com/api/openid.connect.userInfo").mock(
            return_value=httpx.Response(
                200,
                json={
                    "ok": True,
                    "sub": "U123ABC456",
                    "name": "John Doe",
                    "email": "john@example.com",
                    "picture": "https://example.com/avatar.jpg",
                    "email_verified": True,
                },
            )
        )

        result = await SlackOAuth.get_user_info("test-token")

        assert result is not None
        assert result["sub"] == "U123ABC456"
        assert result["name"] == "John Doe"
        assert result["email"] == "john@example.com"

    @pytest.mark.asyncio
    async def test_get_user_info_failure_not_ok(self, respx_mock):
        """Test user info retrieval failure when ok is false."""
        respx_mock.get("https://slack.com/api/openid.connect.userInfo").mock(
            return_value=httpx.Response(
                200,
                json={
                    "ok": False,
                    "error": "invalid_auth",
                },
            )
        )

        result = await SlackOAuth.get_user_info("invalid-token")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_user_info_failure_http_error(self, respx_mock):
        """Test user info retrieval failure on HTTP error."""
        respx_mock.get("https://slack.com/api/openid.connect.userInfo").mock(
            return_value=httpx.Response(401)
        )

        result = await SlackOAuth.get_user_info("invalid-token")

        assert result is None


class TestMockOAuthSlackFormat:
    """Tests for MockOAuthUser Slack format conversion."""

    def test_to_slack_format_contains_required_fields(self):
        """Test that Slack format contains all required fields (OpenID Connect)."""
        mock_user = get_mock_user("alice")
        slack_format = mock_user.to_slack_format()

        assert "ok" in slack_format
        assert slack_format["ok"] is True
        assert "sub" in slack_format
        assert "name" in slack_format
        assert "email" in slack_format
        assert "picture" in slack_format
        assert "email_verified" in slack_format

    def test_to_slack_format_uses_sub_instead_of_id(self):
        """Test that Slack format uses 'sub' field (OpenID Connect standard)."""
        mock_user = MockOAuthUser(
            id="test-123",
            email="test@example.com",
            name="Test User",
            picture="https://example.com/avatar.png",
        )
        slack_format = mock_user.to_slack_format()

        assert slack_format["sub"] == "test-123"
        assert "id" not in slack_format


class TestSlackMockLogin:
    """Tests for Slack mock login endpoint."""

    @pytest.mark.asyncio
    async def test_mock_login_slack_provider(self, client):
        """Test mock login with Slack provider."""
        response = await client.get("/api/v1/auth/mock/login?user=alice&provider=slack")

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["provider"] == "slack"
        assert data["mock_user"] == "alice"

    @pytest.mark.asyncio
    async def test_mock_login_slack_creates_user(self, client):
        """Test that mock login creates user in database."""
        response = await client.get("/api/v1/auth/mock/login?user=bob&provider=slack")

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "bob@example.com"
