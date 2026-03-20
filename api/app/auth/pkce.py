"""PKCE (Proof Key for Code Exchange) implementation."""

import base64
import hashlib
import secrets

PKCE_CODE_VERIFIER_MIN_LENGTH = 43
PKCE_CODE_VERIFIER_MAX_LENGTH = 128


def generate_code_verifier() -> str:
    """Generate a cryptographically random code verifier."""
    return secrets.token_urlsafe(64)


def validate_code_verifier(code_verifier: str) -> None:
    """Validate PKCE code_verifier length bounds defined by RFC 7636."""
    verifier_length = len(code_verifier)
    if (
        verifier_length < PKCE_CODE_VERIFIER_MIN_LENGTH
        or verifier_length > PKCE_CODE_VERIFIER_MAX_LENGTH
    ):
        raise ValueError("code_verifier must be between 43 and 128 characters")


def generate_code_challenge(code_verifier: str) -> str:
    """Generate code challenge from code verifier using S256 method."""
    validate_code_verifier(code_verifier)
    digest = hashlib.sha256(code_verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def verify_code_challenge(code_verifier: str, code_challenge: str) -> bool:
    """Verify that code_verifier matches code_challenge."""
    expected = generate_code_challenge(code_verifier)
    return secrets.compare_digest(expected, code_challenge)
