"""Image-related schemas for API input/output"""

from pydantic import BaseModel, Field
from typing import Optional


# ==================== Output Schemas ====================

class UploadImageResponse(BaseModel):
    """Upload image response (returns full URLs)

    URLs are complete and ready to use - can be embedded in messages
    and accessed by anyone (including AI agents).
    """

    image_id: str = Field(..., description="UUID for image")
    url: str = Field(
        ...,
        description="Full URL to access original image (e.g., https://api.example.com/api/files/images/{image_id})"
    )
    thumbnail_url: Optional[str] = Field(
        None,
        description="Full URL to access thumbnail (e.g., https://api.example.com/api/files/thumbnails/{image_id})"
    )
    filename: str = Field(..., description="Original filename")
    mime_type: str = Field(..., description="MIME type")
    file_size: int = Field(..., description="File size in bytes")
    width: Optional[int] = Field(None, description="Image width in pixels")
    height: Optional[int] = Field(None, description="Image height in pixels")

    class Config:
        from_attributes = True
