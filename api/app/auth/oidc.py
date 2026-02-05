"""OIDC-compatible ID Token generation for non-OIDC providers.

This module generates ID Tokens in OIDC format for OAuth providers
that don't natively support OpenID Connect (GitHub, X, Facebook, Discord, Twitch).
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt

from app.config import get_settings

settings = get_settings()

# RSA key pair for signing ID tokens (generated once at startup)
_private_key: rsa.RSAPrivateKey | None = None
_public_key: rsa.RSAPublicKey | None = None
_key_id: str | None = None


def _ensure_keys() -> None:
    """Ensure RSA key pair is generated."""
    global _private_key, _public_key, _key_id

    if _private_key is None:
        _private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        _public_key = _private_key.public_key()
        _key_id = uuid.uuid4().hex[:16]


def get_private_key_pem() -> bytes:
    """Get private key in PEM format."""
    _ensure_keys()
    assert _private_key is not None
    return _private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def get_public_key_pem() -> bytes:
    """Get public key in PEM format."""
    _ensure_keys()
    assert _public_key is not None
    return _public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def get_jwks() -> dict[str, Any]:
    """Get JSON Web Key Set for public key verification."""
    _ensure_keys()
    assert _public_key is not None
    assert _key_id is not None

    # Get public key numbers
    public_numbers = _public_key.public_numbers()

    # Convert to base64url encoding
    import base64

    def int_to_base64url(n: int, length: int) -> str:
        data = n.to_bytes(length, byteorder="big")
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

    # RSA 2048 = 256 bytes
    n_b64 = int_to_base64url(public_numbers.n, 256)
    e_b64 = int_to_base64url(public_numbers.e, 3)

    return {
        "keys": [
            {
                "kty": "RSA",
                "use": "sig",
                "alg": "RS256",
                "kid": _key_id,
                "n": n_b64,
                "e": e_b64,
            }
        ]
    }


def create_id_token(
    user_id: str,
    email: str,
    provider: str,
    provider_user_id: str,
    display_name: str | None = None,
    avatar_url: str | None = None,
    nonce: str | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Create an OIDC-compatible ID Token.

    Args:
        user_id: Internal YESOD user ID (UUID)
        email: User's email address
        provider: OAuth provider name (github, discord, etc.)
        provider_user_id: User ID from the OAuth provider
        display_name: User's display name
        avatar_url: User's avatar URL
        nonce: Optional nonce for replay protection
        extra_claims: Additional claims to include

    Returns:
        Signed JWT ID Token
    """
    _ensure_keys()
    assert _key_id is not None

    now = datetime.now(UTC)
    expires = now + timedelta(hours=1)

    # Standard OIDC claims
    claims: dict[str, Any] = {
        # Required claims
        "iss": settings.API_URL,  # Issuer
        "sub": user_id,  # Subject (YESOD user ID)
        "aud": settings.API_URL,  # Audience
        "exp": int(expires.timestamp()),  # Expiration
        "iat": int(now.timestamp()),  # Issued at
        # Standard claims
        "email": email,
        "email_verified": True,  # Assumed verified via OAuth
        # Custom claims for provider info
        "provider": provider,
        "provider_sub": provider_user_id,
    }

    # Optional standard claims
    if display_name:
        claims["name"] = display_name

    if avatar_url:
        claims["picture"] = avatar_url

    if nonce:
        claims["nonce"] = nonce

    # Add extra claims
    if extra_claims:
        claims.update(extra_claims)

    # Sign with RSA private key
    return jwt.encode(
        claims,
        get_private_key_pem(),
        algorithm="RS256",
        headers={"kid": _key_id},
    )


def verify_id_token(token: str) -> dict[str, Any] | None:
    """Verify an ID Token and return claims.

    Args:
        token: JWT ID Token to verify

    Returns:
        Token claims if valid, None otherwise
    """
    try:
        claims = jwt.decode(
            token,
            get_public_key_pem(),
            algorithms=["RS256"],
            audience=settings.API_URL,
            issuer=settings.API_URL,
        )
        return claims
    except Exception:
        return None


# Provider-specific claim mappers
def map_github_to_oidc(user_info: dict[str, Any]) -> dict[str, Any]:
    """Map GitHub user info to OIDC claims."""
    return {
        "preferred_username": user_info.get("login"),
        "profile": user_info.get("html_url"),
        "website": user_info.get("blog") or None,
        "locale": None,
        "zoneinfo": None,
    }


def map_discord_to_oidc(user_info: dict[str, Any]) -> dict[str, Any]:
    """Map Discord user info to OIDC claims."""
    return {
        "preferred_username": user_info.get("username"),
        "locale": user_info.get("locale"),
        "zoneinfo": None,
    }


def map_x_to_oidc(user_info: dict[str, Any]) -> dict[str, Any]:
    """Map X (Twitter) user info to OIDC claims."""
    return {
        "preferred_username": user_info.get("username"),
        "profile": f"https://x.com/{user_info.get('username', '')}",
        "locale": None,
        "zoneinfo": None,
    }


def map_facebook_to_oidc(user_info: dict[str, Any]) -> dict[str, Any]:
    """Map Facebook user info to OIDC claims."""
    return {
        "profile": f"https://facebook.com/{user_info.get('id', '')}",
        "locale": user_info.get("locale"),
        "zoneinfo": None,
    }


def map_twitch_to_oidc(user_info: dict[str, Any]) -> dict[str, Any]:
    """Map Twitch user info to OIDC claims."""
    return {
        "preferred_username": user_info.get("login"),
        "profile": f"https://twitch.tv/{user_info.get('login', '')}",
        "locale": None,
        "zoneinfo": None,
    }
