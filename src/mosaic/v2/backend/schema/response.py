"""
Response schemas for API endpoints.

This module defines the unified response format for all API endpoints:
- BaseResponse: Common fields for all responses
- SuccessResponse: Generic successful response wrapper
- ErrorResponse: Error response with error details
- PaginatedData: Generic paginated data structure
"""

from typing import TypeVar, Generic, List, Optional, Any
from pydantic import BaseModel, Field


T = TypeVar('T')


class BaseResponse(BaseModel):
    """Base response model with common fields."""

    success: bool = Field(..., description="Indicates whether the request was successful")
    message: Optional[str] = Field(None, description="Optional message for additional context")


class SuccessResponse(BaseResponse, Generic[T]):
    """Generic successful response wrapper.

    Example:
        SuccessResponse[User] for single user response
        SuccessResponse[PaginatedData[User]] for paginated user list
    """

    success: bool = Field(True, description="Always true for successful responses")
    data: T = Field(..., description="Response data")


class ErrorResponse(BaseResponse):
    """Error response with detailed error information."""

    success: bool = Field(False, description="Always false for error responses")
    data: None = Field(None, description="Always null for error responses")
    error: Optional[dict] = Field(
        None,
        description="Error details including code and optional details",
        examples=[
            {"code": "NOT_FOUND"},
            {"code": "VALIDATION_ERROR", "details": [{"field": "email", "message": "Invalid format"}]}
        ]
    )


class PaginatedData(BaseModel, Generic[T]):
    """Generic paginated data structure.

    Contains both the data items and pagination metadata.
    """

    items: List[T] = Field(..., description="List of items for current page")
    total: int = Field(..., description="Total number of items across all pages", ge=0)
    page: int = Field(..., description="Current page number", ge=1)
    page_size: int = Field(..., description="Number of items per page", ge=1)
    total_pages: int = Field(..., description="Total number of pages", ge=0)
