"""Dependency injection functions for FastAPI routes"""

from typing import AsyncGenerator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession


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
