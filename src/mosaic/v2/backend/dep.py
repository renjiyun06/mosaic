"""Dependency injection functions for FastAPI routes"""

import logging
from typing import AsyncGenerator

from fastapi import Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from .security import verify_token_and_get_user
from .model import User

logger = logging.getLogger(__name__)

# HTTP Bearer token scheme for JWT authentication
security_scheme = HTTPBearer()


async def get_db_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Get async database session from app state

    This dependency provides a database session to route handlers.
    The session is automatically committed on success or rolled back on exception.

    Usage:
        from typing import Annotated
        from fastapi import Depends

        SessionDep = Annotated[AsyncSession, Depends(get_db_session)]

        @router.post("/example")
        async def example_route(session: SessionDep):
            # Use session here
            result = await session.execute(select(User))
            ...

    Args:
        request: FastAPI request object (injected automatically)

    Yields:
        AsyncSession: Database session for this request

    Note:
        - Session is created from the factory stored in app.state
        - Automatically commits on success
        - Automatically rolls back on exception
        - Session is closed after the request completes
    """
    async_session_factory = request.app.state.async_session_factory

    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    session: AsyncSession = Depends(get_db_session),
) -> User:
    """Get current authenticated user from JWT token (HTTP API)

    This dependency extracts the JWT token from the Authorization header,
    decodes it, retrieves the user from database, and returns the user object.

    Usage:
        from typing import Annotated
        from fastapi import Depends

        CurrentUserDep = Annotated[User, Depends(get_current_user)]

        @router.get("/me")
        async def get_me(current_user: CurrentUserDep):
            # current_user is automatically injected
            return current_user

    Args:
        request: FastAPI request object (injected automatically)
        credentials: HTTP Bearer credentials (injected automatically)
        session: Database session (injected automatically)

    Returns:
        User: Authenticated user object

    Raises:
        AuthenticationError: If token is invalid, expired, or user not found
    """
    # Extract token from Authorization header
    token = credentials.credentials

    # Get JWT config from app state
    jwt_config = request.app.state.config.get("jwt", {})

    # Delegate to shared verification function in security module
    return await verify_token_and_get_user(token, jwt_config, session)
