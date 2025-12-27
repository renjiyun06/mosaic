"""Security utilities for password hashing and JWT token handling"""

import hashlib
import logging
from datetime import datetime, timedelta
from typing import Any

from jose import jwt, JWTError
from passlib.context import CryptContext

logger = logging.getLogger(__name__)

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
    return hashlib.sha256(password.encode("utf-8")).hexdigest().encode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hashed password

    Args:
        plain_password: Plain text password
        hashed_password: Hashed password from database

    Returns:
        True if password matches, False otherwise
    """
    normalized = _normalize_password(plain_password)
    return pwd_context.verify(normalized, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash password using bcrypt with SHA256 normalization

    Args:
        password: Plain text password

    Returns:
        Hashed password string
    """
    normalized = _normalize_password(password)
    return pwd_context.hash(normalized)


def create_access_token(user_id: int, jwt_config: dict) -> str:
    """Create JWT access token for user

    Args:
        user_id: User ID to encode in token (integer)
        jwt_config: JWT configuration dict with keys:
            - secret_key: Secret key for signing
            - algorithm: JWT algorithm (e.g., "HS256")
            - access_token_expire_minutes: Token expiration time in minutes

    Returns:
        Encoded JWT token string

    Raises:
        Exception: Failed to create token
    """
    # Calculate expiration time (using local time)
    expire_minutes = jwt_config.get("access_token_expire_minutes", 10080)  # Default 7 days
    expire = datetime.now() + timedelta(minutes=expire_minutes)

    # Prepare payload
    payload = {
        "sub": str(user_id),  # Subject: user ID
        "exp": expire,   # Expiration time
    }

    try:
        # Encode JWT
        encoded_jwt = jwt.encode(
            payload,
            jwt_config["secret_key"],
            algorithm=jwt_config.get("algorithm", "HS256"),
        )
        logger.debug(f"Created access token for user: {user_id}")
        return encoded_jwt
    except Exception as e:
        logger.exception(f"Failed to create access token for user {user_id}")
        raise


def decode_access_token(token: str, jwt_config: dict) -> dict[str, Any] | None:
    """Decode and validate JWT access token

    Args:
        token: JWT token string
        jwt_config: JWT configuration dict with keys:
            - secret_key: Secret key for verification
            - algorithm: JWT algorithm (e.g., "HS256")

    Returns:
        Decoded payload dict if valid, None if invalid/expired
    """
    try:
        payload = jwt.decode(
            token,
            jwt_config["secret_key"],
            algorithms=[jwt_config.get("algorithm", "HS256")],
        )
        return payload
    except JWTError as e:
        logger.debug(f"Failed to decode JWT token: {e}")
        return None
