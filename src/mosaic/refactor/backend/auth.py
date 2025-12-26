"""Authentication utilities"""
import hashlib
from datetime import datetime, timedelta
from typing import Any
from jose import jwt, JWTError
from passlib.context import CryptContext
from .config import settings
from .logger import get_logger

logger = get_logger(__name__)

# Password encryption context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _normalize_password(password: str) -> bytes:
    """Normalize password to handle bcrypt's 72-byte limitation

    Uses SHA256 to hash the password first, ensuring it fits within
    bcrypt's 72-byte limit while maintaining security for long passwords.

    Args:
        password: Plain text password

    Returns:
        Normalized password bytes suitable for bcrypt
    """
    # Use SHA256 to hash the password first
    # This ensures the input to bcrypt is always 64 hex chars (32 bytes)
    return hashlib.sha256(password.encode('utf-8')).hexdigest().encode('utf-8')


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    """Verify password

    Args:
        plain_password: Plain text password
        hashed_password: Hashed password

    Returns:
        True if password matches, False otherwise
    """
    normalized = _normalize_password(plain_password)
    return pwd_context.verify(normalized, hashed_password)


def get_password_hash(password: str) -> str:
    """Get password hash

    Args:
        password: Plain text password

    Returns:
        Hashed password
    """
    normalized = _normalize_password(password)
    return pwd_context.hash(normalized)


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """Create access token (JWT)

    Args:
        data: Data to encode in token
        expires_delta: Token expiration time delta

    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now() + expires_delta
    else:
        expire = datetime.now() + timedelta(
            minutes=settings.access_token_expire_minutes
        )

    to_encode.update({"exp": expire})

    try:
        encoded_jwt = jwt.encode(
            to_encode,
            settings.secret_key,
            algorithm=settings.algorithm,
        )
        logger.debug(f"Created access token for subject: {data.get('sub')}")
        return encoded_jwt
    except Exception as e:
        logger.error(f"Failed to create access token: {e}")
        raise


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Decode access token

    Args:
        token: JWT token string

    Returns:
        Decoded payload or None if invalid
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
        return payload
    except JWTError as e:
        logger.debug(f"Failed to decode token: {e}")
        return None


async def verify_websocket_token(token: str, db):
    """
    Verify WebSocket connection token and get user.

    Args:
        token: JWT token string
        db: Database session

    Returns:
        User object

    Raises:
        Exception: If token is invalid or user not found
    """
    from sqlmodel import select
    from .models.user import User

    # Decode token
    payload = decode_access_token(token)
    if not payload:
        raise Exception("Invalid token")

    # Get user ID from token
    user_id: int = payload.get("sub")
    if not user_id:
        raise Exception("Invalid token payload")

    # Get user from database
    result = await db.execute(
        select(User).where(User.id == user_id, User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()

    if not user:
        raise Exception(f"User {user_id} not found")

    logger.debug(f"WebSocket authenticated user: {user.email}")
    return user
