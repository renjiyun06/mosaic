"""Authentication-related request/response models"""
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, field_validator


class SendCodeRequest(BaseModel):
    """Send verification code request"""

    email: EmailStr


class SendCodeResponse(BaseModel):
    """Send verification code response"""

    message: str
    expires_at: datetime


class RegisterRequest(BaseModel):
    """User registration request"""

    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        pattern="^[a-zA-Z0-9_-]+$",
    )
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    verification_code: str = Field(..., min_length=6, max_length=6)

    @field_validator("username")
    @classmethod
    def username_alphanumeric(cls, v: str) -> str:
        """Validate username contains only letters, numbers,
        underscores and hyphens
        """
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError(
                "Username can only contain letters, numbers, "
                "underscores and hyphens"
            )
        return v


class RegisterResponse(BaseModel):
    """User registration response"""

    message: str
    user: "UserResponse"


class LoginRequest(BaseModel):
    """Login request (supports username or email)"""

    username_or_email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=8)


class LoginResponse(BaseModel):
    """Login response"""

    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"


class UserResponse(BaseModel):
    """User information response (excludes sensitive data)"""

    id: int
    username: str
    email: str
    avatar_url: str | None = None
    is_active: bool
    is_verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UpdateProfileRequest(BaseModel):
    """Update user profile request"""

    avatar_url: str | None = Field(default=None, max_length=512)


class UpdateProfileResponse(BaseModel):
    """Update user profile response"""

    message: str
    user: UserResponse


class ChangePasswordRequest(BaseModel):
    """Change password request"""

    current_password: str = Field(..., min_length=8, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def passwords_different(cls, v: str, info) -> str:
        """Validate new password is different from current password"""
        if "current_password" in info.data and v == info.data["current_password"]:
            raise ValueError("New password must be different from current password")
        return v


class ChangePasswordResponse(BaseModel):
    """Change password response"""

    message: str
