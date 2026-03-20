"""Tests for GitHub OAuth implementation."""

import logging
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from app.auth.mock_oauth import MockOAuthUser, get_mock_user
from app.auth.oauth import GitHubOAuth


class TestGitHubOAuthAuthorizeUrl:
    """Tests for GitHub OAuth authorization URL generation."""

    def test_authorize_url_contains_required_params(self):
        """Test that authorize URL contains all required parameters."""
        with patch("app.auth.oauth.settings") as mock_settings:
            mock_settings.GITHUB_CLIENT_ID = "test-client-id"

            url = GitHubOAuth.get_authorize_url(
                redirect_uri="http://localhost:8000/callback",
                state="test-state-123",
            )

            parsed = urlparse(url)
            params = parse_qs(parsed.query)

            assert parsed.scheme == "https"
            assert parsed.netloc == "github.com"
            assert parsed.path == "/login/oauth/authorize"
            assert params["client_id"] == ["test-client-id"]
            assert params["redirect_uri"] == ["http://localhost:8000/callback"]
            assert params["state"] == ["test-state-123"]
            assert "read:user" in params["scope"][0]
            assert "user:email" in params["scope"][0]

    def test_authorize_url_with_pkce(self):
        """Test that PKCE parameters are included when provided."""
        with patch("app.auth.oauth.settings") as mock_settings:
            mock_settings.GITHUB_CLIENT_ID = "test-client-id"

            url = GitHubOAuth.get_authorize_url(
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
            mock_settings.GITHUB_CLIENT_ID = "test-client-id"

            url = GitHubOAuth.get_authorize_url(
                redirect_uri="http://localhost:8000/callback",
                state="test-state-123",
            )

            parsed = urlparse(url)
            params = parse_qs(parsed.query)

            assert "code_challenge" not in params
            assert "code_challenge_method" not in params


class TestGitHubOAuthExchangeCode:
    """Tests for GitHub OAuth code exchange."""

    @pytest.mark.asyncio
    async def test_exchange_code_success(self, respx_mock):
        """Test successful code exchange."""
        respx_mock.post("https://github.com/login/oauth/access_token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "gho_test_token",
                    "token_type": "bearer",
                    "scope": "read:user,user:email",
                },
            )
        )

        with patch("app.auth.oauth.settings") as mock_settings:
            mock_settings.GITHUB_CLIENT_ID = "test-client-id"
            mock_settings.GITHUB_CLIENT_SECRET = "test-client-secret"

            result = await GitHubOAuth.exchange_code(
                code="test-code",
                redirect_uri="http://localhost:8000/callback",
            )

            assert result is not None
            assert result["access_token"] == "gho_test_token"

    @pytest.mark.asyncio
    async def test_exchange_code_with_pkce(self, respx_mock):
        """Test code exchange with PKCE verifier."""
        respx_mock.post("https://github.com/login/oauth/access_token").mock(
            return_value=httpx.Response(200, json={"access_token": "gho_test_token"})
        )

        with patch("app.auth.oauth.settings") as mock_settings:
            mock_settings.GITHUB_CLIENT_ID = "test-client-id"
            mock_settings.GITHUB_CLIENT_SECRET = "test-client-secret"

            result = await GitHubOAuth.exchange_code(
                code="test-code",
                redirect_uri="http://localhost:8000/callback",
                code_verifier="test-verifier",
            )

            assert result is not None

    @pytest.mark.asyncio
    async def test_exchange_code_failure(self, respx_mock):
        """Test code exchange failure."""
        respx_mock.post("https://github.com/login/oauth/access_token").mock(
            return_value=httpx.Response(400)
        )

        with patch("app.auth.oauth.settings") as mock_settings:
            mock_settings.GITHUB_CLIENT_ID = "test-client-id"
            mock_settings.GITHUB_CLIENT_SECRET = "test-client-secret"

            result = await GitHubOAuth.exchange_code(
                code="invalid-code",
                redirect_uri="http://localhost:8000/callback",
            )

            assert result is None

    @pytest.mark.asyncio
    async def test_exchange_code_failure_logs_normalized_redirect_uri(self, respx_mock, caplog):
        """redirect_uri 不一致調査向けに正規化前後の診断ログを残す。"""
        respx_mock.post("https://github.com/login/oauth/access_token").mock(
            return_value=httpx.Response(
                400,
                text='{"error":"redirect_uri_mismatch","code":"secret-code"}',
            )
        )

        with patch("app.auth.oauth.settings") as mock_settings:
            mock_settings.GITHUB_CLIENT_ID = "test-client-id"
            mock_settings.GITHUB_CLIENT_SECRET = "test-client-secret"
            with caplog.at_level(logging.DEBUG, logger="app.auth.oauth"):
                result = await GitHubOAuth.exchange_code(
                    code="invalid-code",
                    redirect_uri="HTTPS://EXAMPLE.COM:443/api/v1/auth/github/callback/?code=abcdef123456",
                )

        assert result is None
        logs = "\n".join(caplog.messages)
        assert "redirect_uri_raw=https://EXAMPLE.COM:443/api/v1/auth/github/callback/?code=abcd%2A%2A%2A" in logs
        assert "redirect_uri_normalized=https://example.com/api/v1/auth/github/callback?code=abcd%2A%2A%2A" in logs
        assert "redirect_uri_changed=True" in logs
        assert '"code":"***"' in logs


class TestGitHubOAuthUserInfo:
    """Tests for GitHub OAuth user info retrieval."""

    @pytest.mark.asyncio
    async def test_get_user_info_with_public_email(self, respx_mock):
        """Test getting user info when email is public."""
        respx_mock.get("https://api.github.com/user").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": 12345678,
                    "login": "octocat",
                    "name": "The Octocat",
                    "email": "octocat@github.com",
                    "avatar_url": "https://avatars.githubusercontent.com/u/12345678",
                },
            )
        )

        result = await GitHubOAuth.get_user_info("test-token")

        assert result is not None
        assert result["id"] == 12345678
        assert result["login"] == "octocat"
        assert result["email"] == "octocat@github.com"

    @pytest.mark.asyncio
    async def test_get_user_info_with_private_email(self, respx_mock):
        """Test getting user info when email is private (fetches from emails API)."""
        respx_mock.get("https://api.github.com/user").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": 12345678,
                    "login": "octocat",
                    "name": "The Octocat",
                    "email": None,
                    "avatar_url": "https://avatars.githubusercontent.com/u/12345678",
                },
            )
        )
        respx_mock.get("https://api.github.com/user/emails").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"email": "octocat@github.com", "primary": True, "verified": True},
                    {
                        "email": "octocat@users.noreply.github.com",
                        "primary": False,
                        "verified": True,
                    },
                ],
            )
        )

        result = await GitHubOAuth.get_user_info("test-token")

        assert result is not None
        assert result["email"] == "octocat@github.com"

    @pytest.mark.asyncio
    async def test_get_user_info_failure(self, respx_mock):
        """Test user info retrieval failure."""
        respx_mock.get("https://api.github.com/user").mock(return_value=httpx.Response(401))

        result = await GitHubOAuth.get_user_info("invalid-token")

        assert result is None


class TestMockOAuthGitHubFormat:
    """Tests for MockOAuthUser GitHub format conversion."""

    def test_to_github_format_contains_required_fields(self):
        """Test that GitHub format contains all required fields."""
        mock_user = get_mock_user("alice")
        github_format = mock_user.to_github_format()

        assert "id" in github_format
        assert "login" in github_format
        assert "name" in github_format
        assert "email" in github_format
        assert "avatar_url" in github_format

    def test_to_github_format_id_is_numeric(self):
        """Test that GitHub format ID is numeric."""
        mock_user = get_mock_user("alice")
        github_format = mock_user.to_github_format()

        assert isinstance(github_format["id"], int)

    def test_to_github_format_login_is_lowercase(self):
        """Test that GitHub format login is lowercase without spaces."""
        mock_user = MockOAuthUser(
            id="test-123",
            email="test@example.com",
            name="Test User",
            picture="https://example.com/avatar.png",
        )
        github_format = mock_user.to_github_format()

        assert github_format["login"] == "testuser"
        assert " " not in github_format["login"]


class TestGitHubMockLogin:
    """Tests for GitHub mock login endpoint."""

    @pytest.mark.asyncio
    async def test_mock_login_github_provider(self, client):
        """Test mock login with GitHub provider."""
        response = await client.get("/api/v1/auth/mock/login?user=alice&provider=github")

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["provider"] == "github"
        assert data["mock_user"] == "alice"

    @pytest.mark.asyncio
    async def test_mock_login_github_creates_user(self, client):
        """Test that mock login creates user in database."""
        response = await client.get("/api/v1/auth/mock/login?user=bob&provider=github")

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "bob@example.com"


class TestGitHubOAuthCallback:
    """Tests for GitHub OAuth callback endpoint."""

    @pytest.mark.asyncio
    async def test_callback_rejects_mismatched_state(self, client):
        """State mismatch must fail callback to protect against CSRF replay."""
        with (
            patch("app.auth.rate_limit.limiter._check_request_limit", return_value=None),
            patch(
                "app.auth.router.OAuthStateStore.get_and_delete",
                new=AsyncMock(return_value=None),
            ),
        ):
            response = await client.get(
                "/api/v1/auth/github/callback?code=test-code&state=unexpected-state"
            )

        assert response.status_code == 400
        assert response.json() == {"detail": "Invalid or expired state"}

    @pytest.mark.asyncio
    async def test_callback_mismatched_state_logs_request_id(self, client):
        """State mismatch audit log must include provider and request-id."""
        with (
            patch("app.auth.rate_limit.limiter._check_request_limit", return_value=None),
            patch(
                "app.auth.router.OAuthStateStore.get_and_delete",
                new=AsyncMock(return_value=None),
            ),
            patch("app.auth.router.AuditLogger.log_login", new=AsyncMock()) as mock_log_login,
        ):
            response = await client.get(
                "/api/v1/auth/github/callback?code=test-code&state=unexpected-state",
                headers={"X-Request-Id": "req-test-123"},
            )

        assert response.status_code == 400
        assert response.json() == {"detail": "Invalid or expired state"}
        assert mock_log_login.await_count == 1
        assert (
            mock_log_login.await_args.args[6]
            == "Invalid state [provider=github] [request-id=req-test-123]"
        )

    @pytest.mark.asyncio
    async def test_callback_unknown_error_code_records_metric(self, client):
        """Unknown OAuth error code should increment dedicated classification metric."""
        with (
            patch("app.auth.rate_limit.limiter._check_request_limit", return_value=None),
            patch("app.auth.router.record_oauth_failure_metric") as mock_metric,
            patch("app.auth.router.AuditLogger.log_login", new=AsyncMock()) as mock_log_login,
        ):
            response = await client.get("/api/v1/auth/github/callback?error=provider_outage&state=s1")

        assert response.status_code == 400
        assert response.json() == {"detail": "OAuth callback failed: provider_outage"}
        mock_metric.assert_called_once_with("github", "unknown_error_code")
        assert mock_log_login.await_count == 1
        assert mock_log_login.await_args.args[6] == "OAuth callback failed: provider_outage"

    @pytest.mark.asyncio
    async def test_callback_known_error_code_does_not_record_unknown_metric(self, client):
        """Known OAuth error code should not be counted as unknown classification."""
        with (
            patch("app.auth.rate_limit.limiter._check_request_limit", return_value=None),
            patch("app.auth.router.record_oauth_failure_metric") as mock_metric,
            patch("app.auth.router.AuditLogger.log_login", new=AsyncMock()) as mock_log_login,
        ):
            response = await client.get("/api/v1/auth/github/callback?error=access_denied&state=s1")

        assert response.status_code == 400
        assert response.json() == {"detail": "OAuth callback failed: access_denied"}
        mock_metric.assert_not_called()
        assert mock_log_login.await_count == 1
        assert mock_log_login.await_args.args[6] == "OAuth callback failed: access_denied"
