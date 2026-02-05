"""OIDC Discovery and JWKS endpoints."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.config import get_settings

from .oidc import get_jwks, verify_id_token

settings = get_settings()
router = APIRouter(tags=["oidc"])


@router.get("/.well-known/openid-configuration")
async def openid_configuration():
    """OpenID Connect Discovery endpoint.

    Returns the OpenID Provider Configuration Information.
    """
    return JSONResponse(
        content={
            "issuer": settings.API_URL,
            "authorization_endpoint": f"{settings.API_URL}/api/v1/auth/google",
            "token_endpoint": f"{settings.API_URL}/api/v1/auth/refresh",
            "userinfo_endpoint": f"{settings.API_URL}/api/v1/users/me",
            "jwks_uri": f"{settings.API_URL}/.well-known/jwks.json",
            "response_types_supported": ["code"],
            "subject_types_supported": ["public"],
            "id_token_signing_alg_values_supported": ["RS256"],
            "scopes_supported": ["openid", "email", "profile"],
            "token_endpoint_auth_methods_supported": ["none"],
            "claims_supported": [
                "sub",
                "iss",
                "aud",
                "exp",
                "iat",
                "email",
                "email_verified",
                "name",
                "picture",
                "provider",
                "provider_sub",
                "preferred_username",
                "profile",
                "nonce",
            ],
        }
    )


@router.get("/.well-known/jwks.json")
async def jwks():
    """JSON Web Key Set endpoint.

    Returns the public keys used to verify ID Token signatures.
    """
    return JSONResponse(content=get_jwks())


@router.post("/api/v1/auth/verify-id-token")
async def verify_token(token: str):
    """Verify an ID Token and return its claims.

    This endpoint is for testing/debugging purposes.
    """
    claims = verify_id_token(token)
    if claims is None:
        return JSONResponse(
            status_code=401,
            content={"error": "invalid_token", "error_description": "Token verification failed"},
        )
    return claims
