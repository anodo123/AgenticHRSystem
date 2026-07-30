"""Authentication schemas."""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import List


class TokenResponse(BaseModel):
    """Token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class LoginRequest(BaseModel):
    """Login request."""

    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=6)


class LoginResponse(BaseModel):
    """Login response."""

    user_id: int
    username: str
    email: str
    full_name: str
    roles: List[str]
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    """Refresh token request."""

    refresh_token: str


class UserProfile(BaseModel):
    """User profile response."""

    model_config = {"from_attributes": True}

    id: int
    username: str
    email: str
    full_name: str
    is_active: bool
    roles: List[str]
    last_login: datetime | None


class ChangePasswordRequest(BaseModel):
    """Change password request."""

    current_password: str = Field(..., min_length=6)
    new_password: str = Field(..., min_length=6)
    confirm_password: str = Field(..., min_length=6)


class ChangePasswordResponse(BaseModel):
    """Change password response."""

    success: bool
    message: str
