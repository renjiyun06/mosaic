"""Authentication-related schemas for API input/output"""

from datetime import datetime
from pydantic import BaseModel, Field, EmailStr, field_validator
import re


# ==================== Input Schemas ====================

class SendCodeRequest(BaseModel):
    """Send verification code request"""

    email: EmailStr = Field(
        ...,
        description="Email address to receive verification code",
        examples=["alice@example.com"]
    )


class RegisterRequest(BaseModel):
    """User registration request"""

    username: str = Field(
        ...,
        min_length=2,
        max_length=50,
        description="Username (2-50 chars, must start with letter, can contain letters/numbers/underscores/hyphens)",
        examples=["alice"]
    )
    email: EmailStr = Field(
        ...,
        description="Email address",
        examples=["alice@example.com"]
    )
    password: str = Field(
        ...,
        min_length=8,
        description="Password (at least 8 characters, must contain both letters and numbers)",
        examples=["MySecure123"]
    )
    verification_code: str = Field(
        ...,
        min_length=6,
        max_length=6,
        description="6-digit verification code sent to email",
        examples=["123456"]
    )

    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Validate username format: must start with letter, can contain letters/numbers/underscores/hyphens"""
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_-]*$', v):
            raise ValueError(
                'Username must start with a letter and can only contain letters, numbers, underscores and hyphens'
            )
        return v

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password: must contain both letters and numbers"""
        has_letter = bool(re.search(r'[a-zA-Z]', v))
        has_number = bool(re.search(r'\d', v))

        if not has_letter or not has_number:
            raise ValueError(
                'Password must contain both letters and numbers'
            )
        return v

    @field_validator('verification_code')
    @classmethod
    def validate_verification_code(cls, v: str) -> str:
        """Validate verification code: must be 6 digits"""
        if not re.match(r'^\d{6}$', v):
            raise ValueError(
                'Verification code must be 6 digits'
            )
        return v


class LoginRequest(BaseModel):
    """User login request"""

    username_or_email: str = Field(
        ...,
        description="Username or email address",
        examples=["alice", "alice@example.com"]
    )
    password: str = Field(
        ...,
        description="Password",
        examples=["MySecure123"]
    )


# ==================== Output Schemas ====================

class UserOut(BaseModel):
    """User output schema (safe for API responses, excludes sensitive fields)"""

    id: int = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    email: str = Field(..., description="Email address")
    avatar_url: str | None = Field(None, description="Avatar image URL")
    is_active: bool = Field(..., description="Whether account is active")
    created_at: datetime = Field(..., description="Account creation time")

    class Config:
        from_attributes = True  # Enable ORM mode for SQLModel compatibility


class AuthResponse(BaseModel):
    """Authentication response (for register/login)"""

    user: UserOut = Field(..., description="User information")
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(
        default="bearer",
        description="Token type (always 'bearer')"
    )
