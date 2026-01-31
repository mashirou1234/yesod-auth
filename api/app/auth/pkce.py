"""PKCE (Proof Key for Code Exchange) implementation."""

import base64
import hashlib
import secrets


def generate_code_verifier() -> str:
    """Generate a cryptographically random code verifier."""
    return secrets.token_urlsafe(64)


def generate_code_challenge(code_verifier: str) -> str:
    """Generate code challenge from code verifier using S256 method."""
    digest = hashlib.sha256(code_verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def verify_code_challenge(code_verifier: str, code_challenge: str) -> bool:
    """Verify that code_verifier matches code_challenge."""
    expected = generate_code_challenge(code_verifier)
    return secrets.compare_digest(expected, code_challenge)
