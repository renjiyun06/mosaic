"""User-related data models"""
from datetime import datetime
from sqlmodel import Field
from .base import BaseModel


class User(BaseModel, table=True):
    """User table"""

    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True, max_length=50)
    email: str = Field(index=True, unique=True, max_length=255)
    hashed_password: str = Field(max_length=255)

    # User information
    avatar_url: str | None = Field(default=None, max_length=512)

    # Account status
    is_active: bool = Field(default=True)  # Account enabled/disabled
    is_verified: bool = Field(default=False)  # Email verified


class EmailVerification(BaseModel, table=True):
    """Email verification code table"""

    __tablename__ = "email_verifications"

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(index=True, max_length=255)
    code: str = Field(max_length=10)  # Verification code
    expires_at: datetime = Field(nullable=False)  # Expiration time
    is_used: bool = Field(default=False)  # Whether code is used
