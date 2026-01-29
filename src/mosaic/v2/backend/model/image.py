"""Image attachment model for session messages"""

from typing import Optional
from sqlmodel import Field
from .base import BaseModel


class Image(BaseModel, table=True):
    """
    Image model - stores uploaded images as public resources.

    Images are publicly accessible via UUID-based URLs. The UUID provides
    security through obscurity - without knowing the UUID, images cannot
    be accessed.

    Storage structure:
    - Originals: instance_path/files/images/{image_id}.{ext}
    - Thumbnails: instance_path/files/thumbnails/{image_id}.{ext}

    Lifecycle:
    1. User pastes image → Upload to server → Get full URL
    2. Backend returns: https://api.example.com/api/files/images/{image_id}
    3. Front-end inserts URL into message
    4. Message is sent with full URL
    5. Anyone (including AI agents) can access the image via URL

    Public Access:
    - No authentication required for image access
    - Security through UUID obscurity (128-bit random ID)
    - Suitable for sharing with AI agents and external services
    """

    __tablename__ = "images"

    # Unique identifier (serves as security token)
    image_id: str = Field(
        index=True,
        unique=True,
        description="UUID for image, used in URLs and file paths"
    )

    # File metadata
    filename: str = Field(
        max_length=255,
        description="Original filename from upload"
    )
    file_path: str = Field(
        max_length=512,
        description="Relative path to original image file (from instance_path)"
    )
    thumbnail_path: Optional[str] = Field(
        default=None,
        max_length=512,
        description="Relative path to thumbnail file (from instance_path)"
    )
    mime_type: str = Field(
        max_length=100,
        description="MIME type (e.g., image/png, image/jpeg)"
    )
    file_size: int = Field(
        description="File size in bytes"
    )

    # Image dimensions (optional, extracted during upload)
    width: Optional[int] = Field(
        default=None,
        description="Image width in pixels"
    )
    height: Optional[int] = Field(
        default=None,
        description="Image height in pixels"
    )
