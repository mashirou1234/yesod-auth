"""Auth schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class UserResponse(BaseModel):
    """User response schema."""

    id: uuid.UUID = Field(..., description="Unique user identifier")
    email: str = Field(..., description="User's primary email address")
    display_name: str | None = Field(None, description="User's display name")
    avatar_url: str | None = Field(None, description="URL to user's avatar image")
    created_at: datetime = Field(..., description="Account creation timestamp")

    model_config = {"from_attributes": True}


class OAuthAccountInfo(BaseModel):
    """OAuth account info."""

    provider: str = Field(..., description="OAuth provider name (google, discord)")
    provider_user_id: str = Field(..., description="User ID from the OAuth provider")
    created_at: datetime = Field(..., description="When the account was linked")

    model_config = {"from_attributes": True}


class UserWithAccountsResponse(UserResponse):
    """User with linked OAuth accounts."""

    oauth_accounts: list[OAuthAccountInfo] = Field(
        default_factory=list, description="List of linked OAuth accounts"
    )


class TokenPairResponse(BaseModel):
    """Access and refresh token pair response.

    The access token is short-lived (default 15 minutes) and used for API requests.
    The refresh token is long-lived (default 7 days) and used to obtain new access tokens.
    """

    access_token: str = Field(..., description="JWT access token for API authentication")
    refresh_token: str = Field(..., description="Refresh token for obtaining new access tokens")
    token_type: str = Field(default="bearer", description="Token type (always 'bearer')")


class TokenWithIdTokenResponse(TokenPairResponse):
    """Token response including OIDC-compatible ID Token.

    The ID Token contains user identity claims in OIDC format,
    signed with RS256 for verification via JWKS endpoint.
    """

    id_token: str | None = Field(
        None, description="OIDC-compatible ID Token (JWT signed with RS256)"
    )


class RefreshTokenRequest(BaseModel):
    """Request body for refresh token operations."""

    refresh_token: str = Field(..., description="The refresh token to use or revoke")
