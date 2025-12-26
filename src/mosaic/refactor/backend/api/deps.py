"""Dependency injection"""
from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from ..database import get_session
from ..auth import decode_access_token
from ..models import User
from ..exceptions import AuthenticationError
from ..logger import get_logger

logger = get_logger(__name__)

# HTTP Bearer authentication scheme
security = HTTPBearer()

# Database session dependency
SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(
    session: SessionDep,
    credentials: Annotated[
        HTTPAuthorizationCredentials,
        Depends(security),
    ],
) -> User:
    """Get current authenticated user

    Args:
        session: Database session
        credentials: HTTP authentication credentials

    Returns:
        Current user

    Raises:
        HTTPException: Authentication failed
    """
    token = credentials.credentials

    # Decode token
    payload = decode_access_token(token)
    if payload is None:
        logger.warning("Invalid authentication credentials")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user ID
    user_id = payload.get("sub")
    if user_id is None:
        logger.warning("Missing user ID in token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Query user
    result = await session.execute(
        select(User).where(
            User.id == int(user_id),
            User.deleted_at.is_(None)
        )
    )
    user = result.scalar_one_or_none()

    if user is None:
        logger.warning(f"User not found: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        logger.warning(f"Account disabled: {user.username}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account disabled",
        )

    logger.debug(f"Authenticated user: {user.username} (ID: {user.id})")
    return user


# Current user dependency
CurrentUser = Annotated[User, Depends(get_current_user)]
