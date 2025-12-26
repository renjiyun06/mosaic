"""Connection management API routes"""
from fastapi import APIRouter, Depends, status
from sqlmodel import Session
from typing import Annotated

from ..database import get_session
from ..services.connection_service import ConnectionService
from ..schemas.connection import (
    ConnectionCreateRequest,
    ConnectionUpdateRequest,
    ConnectionResponse,
)
from .deps import get_current_user
from ..models.user import User

router = APIRouter()


@router.post(
    "/mosaics/{mosaic_id}/connections",
    response_model=ConnectionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_connection(
    mosaic_id: int,
    request: ConnectionCreateRequest,
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ConnectionResponse:
    """Create a new connection between two nodes

    Args:
        mosaic_id: Mosaic ID
        request: Connection creation request
        session: Database session
        current_user: Current authenticated user

    Returns:
        Created connection
    """
    return await ConnectionService.create_connection(
        session=session,
        mosaic_id=mosaic_id,
        user_id=current_user.id,
        request=request,
    )


@router.get("/mosaics/{mosaic_id}/connections", response_model=list[ConnectionResponse])
async def list_connections(
    mosaic_id: int,
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[ConnectionResponse]:
    """List all connections in a mosaic

    Args:
        mosaic_id: Mosaic ID
        session: Database session
        current_user: Current authenticated user

    Returns:
        List of connections
    """
    return await ConnectionService.list_connections(
        session=session,
        mosaic_id=mosaic_id,
        user_id=current_user.id,
    )


@router.get(
    "/mosaics/{mosaic_id}/connections/{connection_id}",
    response_model=ConnectionResponse,
)
async def get_connection(
    mosaic_id: int,
    connection_id: int,
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ConnectionResponse:
    """Get a specific connection

    Args:
        mosaic_id: Mosaic ID
        connection_id: Connection ID
        session: Database session
        current_user: Current authenticated user

    Returns:
        Connection details
    """
    return await ConnectionService.get_connection(
        session=session,
        mosaic_id=mosaic_id,
        connection_id=connection_id,
        user_id=current_user.id,
    )


@router.put(
    "/mosaics/{mosaic_id}/connections/{connection_id}",
    response_model=ConnectionResponse,
)
async def update_connection(
    mosaic_id: int,
    connection_id: int,
    request: ConnectionUpdateRequest,
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ConnectionResponse:
    """Update a connection

    Args:
        mosaic_id: Mosaic ID
        connection_id: Connection ID
        request: Connection update request
        session: Database session
        current_user: Current authenticated user

    Returns:
        Updated connection
    """
    return await ConnectionService.update_connection(
        session=session,
        mosaic_id=mosaic_id,
        connection_id=connection_id,
        user_id=current_user.id,
        request=request,
    )


@router.delete(
    "/mosaics/{mosaic_id}/connections/{connection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_connection(
    mosaic_id: int,
    connection_id: int,
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Delete a connection

    Args:
        mosaic_id: Mosaic ID
        connection_id: Connection ID
        session: Database session
        current_user: Current authenticated user
    """
    await ConnectionService.delete_connection(
        session=session,
        mosaic_id=mosaic_id,
        connection_id=connection_id,
        user_id=current_user.id,
    )
