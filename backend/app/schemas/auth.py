"""Authentication request and response schemas."""

import uuid
from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    """Sign-in credentials."""

    email: str = Field(..., description="User email address")
    password: str = Field(..., description="Plain-text password")


class TokenOut(BaseModel):
    """JWT bearer token response."""

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type, defaults to bearer")


class UserOut(BaseModel):
    """User profile response."""

    id: uuid.UUID = Field(..., description="Unique user identifier")
    email: str = Field(..., description="User email address")
    role: str = Field(..., description="User role (data_engineer, administrator, auditor)")
