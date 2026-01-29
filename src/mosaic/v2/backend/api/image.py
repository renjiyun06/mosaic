"""Image management API endpoints"""

import logging
from pathlib import Path
from typing import Annotated, Optional
from uuid import uuid4
import io

from fastapi import APIRouter, Depends, Request, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from PIL import Image as PILImage

from ..schema.response import SuccessResponse
from ..schema.image import UploadImageResponse
from ..model import Image
from ..dep import get_db_session
from ..exception import NotFoundError, ValidationError, InternalError

logger = logging.getLogger(__name__)

# ==================== Constants ====================

# Allowed MIME types for image upload
ALLOWED_MIME_TYPES = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/gif": "gif",
    "image/webp": "webp",
}

# Maximum file size: 10MB
MAX_FILE_SIZE = 10 * 1024 * 1024

# Thumbnail size
THUMBNAIL_SIZE = (120, 120)

# Router configuration
router = APIRouter(tags=["Image Management"])


# ==================== Type Aliases ====================

SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


# ==================== API Endpoints ====================

@router.post("/images/upload", response_model=SuccessResponse[UploadImageResponse])
async def upload_image(
    file: UploadFile = File(...),
    req: Request = None,
    session: SessionDep = None,
):
    """Upload an image (public access)

    Business logic:
    1. Validate uploaded file:
       - Check file size (max 10MB by default)
       - Validate MIME type (image/png, image/jpeg, image/gif, image/webp)
       - Validate file extension matches MIME type
       - Read image dimensions using PIL/Pillow
    2. Generate unique image_id (UUID)
    3. Save original image:
       - Path: {instance_path}/files/images/{image_id}.{ext}
       - Create parent directories if needed
       - Write file content
    4. Generate thumbnail (optional):
       - Resize to 120x120 (preserve aspect ratio)
       - Path: {instance_path}/files/thumbnails/{image_id}.{ext}
       - Use PIL/Pillow for resizing
    5. Create Image record in database:
       - image_id, filename, file_path, thumbnail_path
       - mime_type, file_size, width, height
    6. Build full URLs and return response:
       - url: https://{host}/api/files/images/{image_id}
       - thumbnail_url: https://{host}/api/files/thumbnails/{image_id}

    Important: URLs returned are FULL URLs (not relative paths) because:
    - They will be embedded in messages seen by AI agents
    - AI agents need complete URLs to access images
    - URLs work across different environments (dev/test/prod)

    Request:
        - file: Image file (multipart/form-data)

    Response:
        {
          "success": true,
          "data": {
            "image_id": "uuid-string",
            "url": "https://api.example.com/api/files/images/{image_id}",
            "thumbnail_url": "https://api.example.com/api/files/thumbnails/{image_id}",
            "filename": "screenshot.png",
            "mime_type": "image/png",
            "file_size": 123456,
            "width": 1920,
            "height": 1080
          }
        }

    Raises:
        ValidationError: Invalid file type or size
        InternalError: Failed to save file or create thumbnail
    """
    # Step 1: Validate MIME type
    mime_type = file.content_type
    if mime_type not in ALLOWED_MIME_TYPES:
        raise ValidationError(
            f"Invalid image type. Allowed types: {', '.join(ALLOWED_MIME_TYPES.keys())}"
        )

    # Read file content
    file_content = await file.read()
    file_size = len(file_content)

    # Step 2: Validate file size
    if file_size > MAX_FILE_SIZE:
        raise ValidationError(
            f"File size exceeds maximum allowed size of {MAX_FILE_SIZE / 1024 / 1024}MB"
        )

    # Step 3: Read image dimensions and validate image content
    try:
        image = PILImage.open(io.BytesIO(file_content))
        width, height = image.size
        image_format = image.format
    except Exception as e:
        logger.error(f"Failed to read image: {e}")
        raise ValidationError("Invalid image file or corrupted image")

    # Step 4: Generate unique image_id
    image_id = str(uuid4())
    file_extension = ALLOWED_MIME_TYPES[mime_type]

    # Step 5: Get instance_path from app state
    instance_path: Path = req.app.state.instance_path

    # Step 6: Save original image
    images_dir = instance_path / "files" / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    image_filename = f"{image_id}.{file_extension}"
    image_path = images_dir / image_filename

    try:
        # Write original image file
        with open(image_path, "wb") as f:
            f.write(file_content)
        logger.info(f"Saved original image: {image_path}")
    except Exception as e:
        logger.error(f"Failed to save image file: {e}")
        raise InternalError("Failed to save image file")

    # Step 7: Generate thumbnail
    thumbnail_path_relative: Optional[str] = None
    thumbnails_dir = instance_path / "files" / "thumbnails"
    thumbnails_dir.mkdir(parents=True, exist_ok=True)

    thumbnail_filename = f"{image_id}.{file_extension}"
    thumbnail_path = thumbnails_dir / thumbnail_filename

    try:
        # Create thumbnail (preserve aspect ratio)
        image.thumbnail(THUMBNAIL_SIZE, PILImage.Resampling.LANCZOS)
        image.save(thumbnail_path)
        thumbnail_path_relative = f"files/thumbnails/{thumbnail_filename}"
        logger.info(f"Generated thumbnail: {thumbnail_path}")
    except Exception as e:
        logger.warning(f"Failed to generate thumbnail: {e}")
        # Continue without thumbnail (it's optional)

    # Step 8: Create database record
    image_record = Image(
        image_id=image_id,
        filename=file.filename or image_filename,
        file_path=f"files/images/{image_filename}",
        thumbnail_path=thumbnail_path_relative,
        mime_type=mime_type,
        file_size=file_size,
        width=width,
        height=height,
    )

    session.add(image_record)
    await session.commit()
    await session.refresh(image_record)

    logger.info(f"Created image record: {image_id}")

    # Step 9: Build full URLs
    # Get base URL from request
    base_url = str(req.base_url).rstrip("/")

    url = f"{base_url}/api/files/images/{image_id}"
    thumbnail_url = f"{base_url}/api/files/thumbnails/{image_id}" if thumbnail_path_relative else None

    # Step 10: Return response
    return SuccessResponse(
        data=UploadImageResponse(
            image_id=image_id,
            url=url,
            thumbnail_url=thumbnail_url,
            filename=file.filename or image_filename,
            mime_type=mime_type,
            file_size=file_size,
            width=width,
            height=height,
        )
    )


@router.get("/files/images/{image_id}", response_class=FileResponse)
async def get_image(
    image_id: str,
    req: Request = None,
    session: SessionDep = None,
) -> FileResponse:
    """Get original image file (public access, no auth required)

    Business logic:
    1. Query image from database:
       - SELECT * FROM images WHERE image_id={image_id} AND deleted_at IS NULL
    2. Check file exists:
       - Construct file path: {instance_path}/{image.file_path}
       - Verify file exists on disk
    3. Return file response:
       - Use FastAPI FileResponse
       - Set correct Content-Type header (image.mime_type)
       - Set Content-Disposition: inline (display in browser)

    Public Access:
    - No authentication required
    - Security through UUID obscurity (128-bit random ID)
    - Suitable for sharing with AI agents and embedding in messages

    Path Parameters:
        - image_id: Image UUID

    Returns:
        FileResponse: Binary image file with headers:
          - Content-Type: image/png | image/jpeg | image/gif | image/webp
          - Content-Disposition: inline; filename="original_filename.ext"

    Raises:
        NotFoundError: Image not found in database or file missing

    Example:
        GET /api/files/images/a1b2c3d4-e5f6-7890-abcd-ef1234567890

        Response Headers:
          Content-Type: image/png
          Content-Disposition: inline; filename="screenshot.png"
          Content-Length: 123456

        Response Body:
          <binary image data>
    """
    # Step 1: Query image from database
    result = await session.execute(
        select(Image).where(Image.image_id == image_id, Image.deleted_at == None)
    )
    image = result.scalar_one_or_none()

    if not image:
        raise NotFoundError(f"Image not found: {image_id}")

    # Step 2: Check file exists on disk
    instance_path: Path = req.app.state.instance_path
    file_path = instance_path / image.file_path

    if not file_path.exists():
        logger.error(f"Image file not found on disk: {file_path}")
        raise NotFoundError(f"Image file not found: {image_id}")

    # Step 3: Return file response
    return FileResponse(
        path=str(file_path),
        media_type=image.mime_type,
        filename=image.filename,
        headers={"Content-Disposition": f'inline; filename="{image.filename}"'}
    )


@router.get("/files/thumbnails/{image_id}", response_class=FileResponse)
async def get_thumbnail(
    image_id: str,
    req: Request = None,
    session: SessionDep = None,
) -> FileResponse:
    """Get image thumbnail (public access, no auth required)

    Business logic:
    1. Query image from database:
       - SELECT * FROM images WHERE image_id={image_id} AND deleted_at IS NULL
    2. Check thumbnail exists:
       - If image.thumbnail_path exists:
         - Construct path: {instance_path}/{image.thumbnail_path}
         - Verify file exists
       - If thumbnail not available, fallback to original image
    3. Return file response:
       - Use FastAPI FileResponse
       - Set correct Content-Type header
       - Set Content-Disposition: inline

    Public Access:
    - No authentication required
    - Security through UUID obscurity
    - Suitable for embedding in messages and previews

    Path Parameters:
        - image_id: Image UUID

    Returns:
        FileResponse: Binary thumbnail file with headers:
          - Content-Type: image/png | image/jpeg | image/gif | image/webp
          - Content-Disposition: inline; filename="thumbnail_original_filename.ext"

    Raises:
        NotFoundError: Image not found in database

    Example:
        GET /api/files/thumbnails/a1b2c3d4-e5f6-7890-abcd-ef1234567890

        Response Headers:
          Content-Type: image/png
          Content-Disposition: inline; filename="screenshot.png"
          Content-Length: 12345

        Response Body:
          <binary thumbnail data>
    """
    # Step 1: Query image from database
    result = await session.execute(
        select(Image).where(Image.image_id == image_id, Image.deleted_at == None)
    )
    image = result.scalar_one_or_none()

    if not image:
        raise NotFoundError(f"Image not found: {image_id}")

    # Step 2: Check thumbnail exists, fallback to original if not
    instance_path: Path = req.app.state.instance_path

    # Try thumbnail first
    if image.thumbnail_path:
        thumbnail_path = instance_path / image.thumbnail_path
        if thumbnail_path.exists():
            # Return thumbnail
            return FileResponse(
                path=str(thumbnail_path),
                media_type=image.mime_type,
                filename=image.filename,
                headers={"Content-Disposition": f'inline; filename="{image.filename}"'}
            )
        else:
            logger.warning(f"Thumbnail file not found, using original: {thumbnail_path}")

    # Fallback to original image
    file_path = instance_path / image.file_path

    if not file_path.exists():
        logger.error(f"Image file not found on disk: {file_path}")
        raise NotFoundError(f"Image file not found: {image_id}")

    # Step 3: Return file response (original image as fallback)
    return FileResponse(
        path=str(file_path),
        media_type=image.mime_type,
        filename=image.filename,
        headers={"Content-Disposition": f'inline; filename="{image.filename}"'}
    )
