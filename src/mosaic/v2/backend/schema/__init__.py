"""
Schema package for API request/response models.
"""

from .response import (
    BaseResponse,
    SuccessResponse,
    ErrorResponse,
    PaginatedData,
)

__all__ = [
    "BaseResponse",
    "SuccessResponse",
    "ErrorResponse",
    "PaginatedData",
]
