"""
Schema package for API request/response models.
"""

from .response import (
    BaseResponse,
    SuccessResponse,
    ErrorResponse,
    PaginatedData,
)
from .auth import (
    SendCodeRequest,
    RegisterRequest,
    LoginRequest,
    UserOut,
    AuthResponse,
)

__all__ = [
    # Response schemas
    "BaseResponse",
    "SuccessResponse",
    "ErrorResponse",
    "PaginatedData",
    # Auth schemas
    "SendCodeRequest",
    "RegisterRequest",
    "LoginRequest",
    "UserOut",
    "AuthResponse",
]
