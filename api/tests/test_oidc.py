"""Tests for OIDC ID Token generation."""

import pytest

from app.auth.oidc import (
    create_id_token,
    get_jwks,
    map_discord_to_oidc,
    map_facebook_to_oidc,
    map_github_to_oidc,
    map_twitch_to_oidc,
    map_x_to_oidc,
    verify_id_token,
)


class TestIdTokenGeneration:
    """Test ID Token creation and verification."""

    def test_create_id_token_basic(self):
        """Test basic ID token creation."""
        token = create_id_token(
            user_id="test-user-123",
            email="test@example.com",
            provider="github",
            provider_user_id="gh-12345",
        )

        assert token is not None
        assert isinstance(token, str)
        # JWT has 3 parts separated by dots
        parts = token.split(".")
        assert len(parts) == 3

    def test_create_id_token_with_claims(self):
        """Test ID token with all claims."""
        token = create_id_token(
            user_id="test-user-456",
            email="user@example.com",
            provider="discord",
            provider_user_id="dc-67890",
            display_name="Test User",
            avatar_url="https://example.com/avatar.png",
            nonce="test-nonce-123",
            extra_claims={"preferred_username": "testuser"},
        )

        assert token is not None
        claims = verify_id_token(token)
        assert claims is not None
        assert claims["sub"] == "test-user-456"
        assert claims["email"] == "user@example.com"
        assert claims["provider"] == "discord"
        assert claims["provider_sub"] == "dc-67890"
        assert claims["name"] == "Test User"
        assert claims["picture"] == "https://example.com/avatar.png"
        assert claims["nonce"] == "test-nonce-123"
        assert claims["preferred_username"] == "testuser"

    def test_verify_id_token_valid(self):
        """Test verification of valid token."""
        token = create_id_token(
            user_id="verify-test",
            email="verify@example.com",
            provider="github",
            provider_user_id="gh-verify",
        )

        claims = verify_id_token(token)
        assert claims is not None
        assert claims["sub"] == "verify-test"
        assert claims["email"] == "verify@example.com"
        assert claims["email_verified"] is True

    def test_verify_id_token_invalid(self):
        """Test verification of invalid token."""
        claims = verify_id_token("invalid.token.here")
        assert claims is None

    def test_verify_id_token_tampered(self):
        """Test verification of tampered token."""
        token = create_id_token(
            user_id="tamper-test",
            email="tamper@example.com",
            provider="github",
            provider_user_id="gh-tamper",
        )

        # Tamper with the token
        parts = token.split(".")
        parts[1] = parts[1] + "tampered"
        tampered_token = ".".join(parts)

        claims = verify_id_token(tampered_token)
        assert claims is None


class TestJWKS:
    """Test JWKS endpoint functionality."""

    def test_get_jwks_structure(self):
        """Test JWKS has correct structure."""
        jwks = get_jwks()

        assert "keys" in jwks
        assert len(jwks["keys"]) == 1

        key = jwks["keys"][0]
        assert key["kty"] == "RSA"
        assert key["use"] == "sig"
        assert key["alg"] == "RS256"
        assert "kid" in key
        assert "n" in key
        assert "e" in key

    def test_jwks_consistency(self):
        """Test JWKS returns same key on multiple calls."""
        jwks1 = get_jwks()
        jwks2 = get_jwks()

        assert jwks1["keys"][0]["kid"] == jwks2["keys"][0]["kid"]
        assert jwks1["keys"][0]["n"] == jwks2["keys"][0]["n"]


class TestProviderMappers:
    """Test provider-specific claim mappers."""

    def test_map_github_to_oidc(self):
        """Test GitHub user info mapping."""
        user_info = {
            "login": "octocat",
            "html_url": "https://github.com/octocat",
            "blog": "https://octocat.blog",
        }

        claims = map_github_to_oidc(user_info)
        assert claims["preferred_username"] == "octocat"
        assert claims["profile"] == "https://github.com/octocat"
        assert claims["website"] == "https://octocat.blog"

    def test_map_discord_to_oidc(self):
        """Test Discord user info mapping."""
        user_info = {
            "username": "discord_user",
            "locale": "en-US",
        }

        claims = map_discord_to_oidc(user_info)
        assert claims["preferred_username"] == "discord_user"
        assert claims["locale"] == "en-US"

    def test_map_x_to_oidc(self):
        """Test X (Twitter) user info mapping."""
        user_info = {
            "username": "x_user",
        }

        claims = map_x_to_oidc(user_info)
        assert claims["preferred_username"] == "x_user"
        assert claims["profile"] == "https://x.com/x_user"

    def test_map_facebook_to_oidc(self):
        """Test Facebook user info mapping."""
        user_info = {
            "id": "fb123456",
            "locale": "ja_JP",
        }

        claims = map_facebook_to_oidc(user_info)
        assert claims["profile"] == "https://facebook.com/fb123456"
        assert claims["locale"] == "ja_JP"

    def test_map_twitch_to_oidc(self):
        """Test Twitch user info mapping."""
        user_info = {
            "login": "twitch_streamer",
        }

        claims = map_twitch_to_oidc(user_info)
        assert claims["preferred_username"] == "twitch_streamer"
        assert claims["profile"] == "https://twitch.tv/twitch_streamer"


@pytest.mark.asyncio
class TestOIDCEndpoints:
    """Test OIDC discovery endpoints."""

    async def test_jwks_endpoint(self, client):
        """Test /.well-known/jwks.json endpoint."""
        response = await client.get("/.well-known/jwks.json")
        assert response.status_code == 200

        data = response.json()
        assert "keys" in data
        assert len(data["keys"]) >= 1

    async def test_openid_configuration_endpoint(self, client):
        """Test /.well-known/openid-configuration endpoint."""
        response = await client.get("/.well-known/openid-configuration")
        assert response.status_code == 200

        data = response.json()
        assert "issuer" in data
        assert "jwks_uri" in data
        assert "id_token_signing_alg_values_supported" in data
        assert "RS256" in data["id_token_signing_alg_values_supported"]
