"""Connection management API endpoints"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Annotated

from ..schema.response import SuccessResponse
from ..schema.connection import (
    CreateConnectionRequest,
    UpdateConnectionRequest,
    ConnectionOut,
)
from ..model import Connection, Node, Subscription, Mosaic
from ..dep import get_db_session, get_current_user
from ..model.user import User
from ..exception import ConflictError, NotFoundError, PermissionError, ValidationError
from ..enum import MosaicStatus

logger = logging.getLogger(__name__)

# Router configuration
router = APIRouter(prefix="/mosaics/{mosaic_id}/connections", tags=["Connection Management"])


# ==================== Type Aliases ====================

SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


# ==================== API Endpoints ====================

@router.post("", response_model=SuccessResponse[ConnectionOut])
async def create_connection(
    mosaic_id: int,
    request: CreateConnectionRequest,
    req: Request,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """Create a new connection between two nodes

    Business logic:
    1. Query mosaic and verify ownership
    2. Verify mosaic is stopped (cannot modify running mosaic)
    3. Verify both source_node and target_node exist in the specified mosaic
    4. Check if connection already exists between these two nodes (prevent duplicate)
    5. Create Connection record
    6. Return created connection

    Validation Rules:
    - Mosaic must exist and belong to current user
    - Mosaic must be stopped (cannot modify running mosaic)
    - source_node_id and target_node_id must exist in the mosaic
    - Self-loops are allowed (node can connect to itself)
    - Unique constraint: (mosaic_id, source_node_id, target_node_id) for non-deleted records

    Raises:
        NotFoundError: If mosaic or nodes not found
        PermissionError: If mosaic doesn't belong to current user
        ValidationError: If mosaic is running
        ConflictError: If connection already exists
    """
    logger.info(
        f"Creating connection: mosaic_id={mosaic_id}, "
        f"source={request.source_node_id}, target={request.target_node_id}, "
        f"user_id={current_user.id}"
    )

    # 1. Query mosaic and verify ownership
    mosaic_stmt = select(Mosaic).where(
        Mosaic.id == mosaic_id,
        Mosaic.deleted_at.is_(None)
    )
    mosaic_result = await session.execute(mosaic_stmt)
    mosaic = mosaic_result.scalar_one_or_none()

    if not mosaic:
        logger.warning(f"Mosaic not found: id={mosaic_id}")
        raise NotFoundError("Mosaic not found")

    if mosaic.user_id != current_user.id:
        logger.warning(
            f"Permission denied: mosaic_id={mosaic_id}, "
            f"owner_id={mosaic.user_id}, requester_id={current_user.id}"
        )
        raise PermissionError("You do not have permission to create connections in this mosaic")

    # 2. Verify mosaic is stopped
    runtime_manager = req.app.state.runtime_manager
    status = await runtime_manager.get_mosaic_status(mosaic)
    if status == MosaicStatus.RUNNING:
        logger.warning(f"Cannot modify running mosaic: id={mosaic_id}")
        raise ValidationError("Cannot create connection in running mosaic. Please stop it first.")

    # 3. Query both nodes in one statement
    stmt = select(Node).where(
        Node.mosaic_id == mosaic_id,
        Node.node_id.in_([request.source_node_id, request.target_node_id]),
        Node.deleted_at.is_(None)
    )
    result = await session.execute(stmt)
    nodes = result.scalars().all()

    # Build node map
    node_map = {node.node_id: node for node in nodes}

    # Verify both nodes exist
    if request.source_node_id not in node_map:
        logger.warning(
            f"Source node not found: mosaic_id={mosaic_id}, node_id={request.source_node_id}"
        )
        raise NotFoundError(f"Source node '{request.source_node_id}' not found in this mosaic")

    if request.target_node_id not in node_map:
        logger.warning(
            f"Target node not found: mosaic_id={mosaic_id}, node_id={request.target_node_id}"
        )
        raise NotFoundError(f"Target node '{request.target_node_id}' not found in this mosaic")

    # 3. Check for existing connection
    existing_stmt = select(Connection).where(
        Connection.mosaic_id == mosaic_id,
        Connection.source_node_id == request.source_node_id,
        Connection.target_node_id == request.target_node_id,
        Connection.deleted_at.is_(None)
    )
    existing_result = await session.execute(existing_stmt)
    existing_connection = existing_result.scalar_one_or_none()

    if existing_connection:
        logger.warning(
            f"Connection already exists: mosaic_id={mosaic_id}, "
            f"source={request.source_node_id}, target={request.target_node_id}"
        )
        raise ConflictError(
            f"Connection from '{request.source_node_id}' to '{request.target_node_id}' already exists"
        )

    # 4. Create Connection record
    connection = Connection(
        user_id=current_user.id,
        mosaic_id=mosaic_id,
        source_node_id=request.source_node_id,
        target_node_id=request.target_node_id,
        session_alignment=request.session_alignment,
        description=request.description
    )
    session.add(connection)
    await session.flush()

    logger.info(
        f"Connection created: id={connection.id}, mosaic_id={mosaic_id}, "
        f"source={request.source_node_id}, target={request.target_node_id}"
    )

    # 5. Construct response
    connection_out = ConnectionOut(
        id=connection.id,
        user_id=connection.user_id,
        mosaic_id=connection.mosaic_id,
        source_node_id=connection.source_node_id,
        target_node_id=connection.target_node_id,
        session_alignment=connection.session_alignment,
        description=connection.description,
        created_at=connection.created_at,
        updated_at=connection.updated_at
    )

    return SuccessResponse(data=connection_out)


@router.get("", response_model=SuccessResponse[list[ConnectionOut]])
async def list_connections(
    mosaic_id: int,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """List all connections in a mosaic

    Business logic:
    1. Query all connections WHERE mosaic_id=X AND user_id=Y AND deleted_at IS NULL
    2. Order by created_at DESC (newest first)
    3. Return list of connections (empty list if none)

    Note: This endpoint does not verify if the mosaic exists. If mosaic doesn't exist
    or doesn't belong to user, it simply returns an empty list.

    Raises:
        (No exceptions raised - returns empty list if no connections found)
    """
    logger.info(f"Listing connections: mosaic_id={mosaic_id}, user_id={current_user.id}")

    # Query all connections for this mosaic and user
    stmt = select(Connection).where(
        Connection.mosaic_id == mosaic_id,
        Connection.user_id == current_user.id,
        Connection.deleted_at.is_(None)
    ).order_by(Connection.created_at.desc())

    result = await session.execute(stmt)
    connections = result.scalars().all()

    logger.debug(
        f"Found {len(connections)} connections: mosaic_id={mosaic_id}, user_id={current_user.id}"
    )

    # Build response list
    connection_list = [
        ConnectionOut(
            id=conn.id,
            user_id=conn.user_id,
            mosaic_id=conn.mosaic_id,
            source_node_id=conn.source_node_id,
            target_node_id=conn.target_node_id,
            session_alignment=conn.session_alignment,
            description=conn.description,
            created_at=conn.created_at,
            updated_at=conn.updated_at
        )
        for conn in connections
    ]

    logger.info(
        f"Listed {len(connection_list)} connections: mosaic_id={mosaic_id}, user_id={current_user.id}"
    )
    return SuccessResponse(data=connection_list)


@router.get("/{connection_id}", response_model=SuccessResponse[ConnectionOut])
async def get_connection(
    mosaic_id: int,
    connection_id: int,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """Get a specific connection

    Business logic:
    1. Query connection WHERE id=connection_id AND mosaic_id=X AND user_id=Y AND deleted_at IS NULL
    2. If not found, raise NotFoundError
    3. Return connection

    Raises:
        NotFoundError: If connection not found or doesn't belong to specified mosaic/user
    """
    logger.info(
        f"Getting connection: id={connection_id}, mosaic_id={mosaic_id}, user_id={current_user.id}"
    )

    # Query connection by ID with mosaic_id and user_id verification
    stmt = select(Connection).where(
        Connection.id == connection_id,
        Connection.mosaic_id == mosaic_id,
        Connection.user_id == current_user.id,
        Connection.deleted_at.is_(None)
    )
    result = await session.execute(stmt)
    connection = result.scalar_one_or_none()

    if not connection:
        logger.warning(
            f"Connection not found: id={connection_id}, mosaic_id={mosaic_id}, "
            f"user_id={current_user.id}"
        )
        raise NotFoundError("Connection not found")

    # Construct response
    connection_out = ConnectionOut(
        id=connection.id,
        user_id=connection.user_id,
        mosaic_id=connection.mosaic_id,
        source_node_id=connection.source_node_id,
        target_node_id=connection.target_node_id,
        session_alignment=connection.session_alignment,
        description=connection.description,
        created_at=connection.created_at,
        updated_at=connection.updated_at
    )

    logger.info(f"Connection retrieved successfully: id={connection_id}")
    return SuccessResponse(data=connection_out)


@router.patch("/{connection_id}", response_model=SuccessResponse[ConnectionOut])
async def update_connection(
    mosaic_id: int,
    connection_id: int,
    request: UpdateConnectionRequest,
    req: Request,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """Update a connection

    Business logic:
    1. Validate request: at least one field (session_alignment or description) must be provided
    2. Query mosaic and verify ownership
    3. Verify mosaic is stopped (cannot modify running mosaic)
    4. Query connection and verify ownership
    5. Update allowed fields (session_alignment, description)
    6. Update updated_at timestamp
    7. Return updated connection

    Note: source_node_id and target_node_id are immutable (cannot be updated)

    Validation Rules:
    - At least one field must be provided for update
    - Mosaic must be stopped (cannot modify running mosaic)
    - source_node_id and target_node_id are immutable

    Raises:
        ValidationError: If no fields provided for update or mosaic is running
        NotFoundError: If mosaic or connection not found
        PermissionError: If mosaic or connection doesn't belong to current user
    """
    logger.info(
        f"Updating connection: id={connection_id}, mosaic_id={mosaic_id}, "
        f"user_id={current_user.id}"
    )

    # 1. Validate request: at least one field must be provided
    if request.session_alignment is None and request.description is None:
        raise ValidationError(
            "At least one field (session_alignment or description) must be provided"
        )

    # 2. Query mosaic and verify ownership
    mosaic_stmt = select(Mosaic).where(
        Mosaic.id == mosaic_id,
        Mosaic.deleted_at.is_(None)
    )
    mosaic_result = await session.execute(mosaic_stmt)
    mosaic = mosaic_result.scalar_one_or_none()

    if not mosaic:
        logger.warning(f"Mosaic not found: id={mosaic_id}")
        raise NotFoundError("Mosaic not found")

    if mosaic.user_id != current_user.id:
        logger.warning(
            f"Permission denied: mosaic_id={mosaic_id}, "
            f"owner_id={mosaic.user_id}, requester_id={current_user.id}"
        )
        raise PermissionError("You do not have permission to modify this mosaic")

    # 3. Verify mosaic is stopped
    runtime_manager = req.app.state.runtime_manager
    status = await runtime_manager.get_mosaic_status(mosaic)
    if status == MosaicStatus.RUNNING:
        logger.warning(f"Cannot modify running mosaic: id={mosaic_id}")
        raise ValidationError("Cannot update connection in running mosaic. Please stop it first.")

    # 4. Query connection and verify ownership
    stmt = select(Connection).where(
        Connection.id == connection_id,
        Connection.mosaic_id == mosaic_id,
        Connection.user_id == current_user.id,
        Connection.deleted_at.is_(None)
    )
    result = await session.execute(stmt)
    connection = result.scalar_one_or_none()

    if not connection:
        logger.warning(
            f"Connection not found: id={connection_id}, mosaic_id={mosaic_id}, "
            f"user_id={current_user.id}"
        )
        raise NotFoundError("Connection not found")

    # 5. Update session_alignment if provided
    if request.session_alignment is not None:
        connection.session_alignment = request.session_alignment
        logger.debug(
            f"Connection session_alignment updated: id={connection_id}, "
            f"new_alignment={request.session_alignment}"
        )

    # 6. Update description if provided
    if request.description is not None:
        connection.description = request.description
        logger.debug(f"Connection description updated: id={connection_id}")

    # 7. Update the updated_at timestamp
    connection.updated_at = datetime.now()

    # 8. Construct response
    connection_out = ConnectionOut(
        id=connection.id,
        user_id=connection.user_id,
        mosaic_id=connection.mosaic_id,
        source_node_id=connection.source_node_id,
        target_node_id=connection.target_node_id,
        session_alignment=connection.session_alignment,
        description=connection.description,
        created_at=connection.created_at,
        updated_at=connection.updated_at
    )

    logger.info(f"Connection updated successfully: id={connection_id}")
    return SuccessResponse(data=connection_out)


@router.delete("/{connection_id}", response_model=SuccessResponse[None])
async def delete_connection(
    mosaic_id: int,
    connection_id: int,
    req: Request,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """Delete a connection (soft delete)

    Business logic:
    1. Query mosaic and verify ownership
    2. Verify mosaic is stopped (cannot modify running mosaic)
    3. Query connection and verify ownership
    4. Validate deletion prerequisites:
       - Connection must have no active subscriptions
         COUNT subscriptions WHERE connection_id=X AND deleted_at IS NULL must be 0
    5. Set deleted_at = datetime.now() (soft delete)
    6. Commit and return success

    Note:
    - This is a soft delete operation (sets deleted_at timestamp)
    - The record remains in database but is excluded from queries
    - Deleted connections don't count toward unique constraint

    Raises:
        NotFoundError: If mosaic or connection not found or already deleted
        PermissionError: If mosaic doesn't belong to current user
        ValidationError: If mosaic is running or connection has active subscriptions (cannot delete)
    """
    logger.info(
        f"Deleting connection: id={connection_id}, mosaic_id={mosaic_id}, "
        f"user_id={current_user.id}"
    )

    # 1. Query mosaic and verify ownership
    mosaic_stmt = select(Mosaic).where(
        Mosaic.id == mosaic_id,
        Mosaic.deleted_at.is_(None)
    )
    mosaic_result = await session.execute(mosaic_stmt)
    mosaic = mosaic_result.scalar_one_or_none()

    if not mosaic:
        logger.warning(f"Mosaic not found: id={mosaic_id}")
        raise NotFoundError("Mosaic not found")

    if mosaic.user_id != current_user.id:
        logger.warning(
            f"Permission denied: mosaic_id={mosaic_id}, "
            f"owner_id={mosaic.user_id}, requester_id={current_user.id}"
        )
        raise PermissionError("You do not have permission to delete connections in this mosaic")

    # 2. Verify mosaic is stopped
    runtime_manager = req.app.state.runtime_manager
    status = await runtime_manager.get_mosaic_status(mosaic)
    if status == MosaicStatus.RUNNING:
        logger.warning(f"Cannot modify running mosaic: id={mosaic_id}")
        raise ValidationError("Cannot delete connection in running mosaic. Please stop it first.")

    # 3. Query connection and verify ownership
    stmt = select(Connection).where(
        Connection.id == connection_id,
        Connection.mosaic_id == mosaic_id,
        Connection.user_id == current_user.id,
        Connection.deleted_at.is_(None)
    )
    result = await session.execute(stmt)
    connection = result.scalar_one_or_none()

    if not connection:
        logger.warning(
            f"Connection not found: id={connection_id}, mosaic_id={mosaic_id}, "
            f"user_id={current_user.id}"
        )
        raise NotFoundError("Connection not found")

    # 4. Check if connection has active subscriptions
    subscription_count_stmt = select(func.count(Subscription.id)).where(
        Subscription.connection_id == connection.id,
        Subscription.deleted_at.is_(None)
    )
    subscription_count_result = await session.execute(subscription_count_stmt)
    subscription_count = subscription_count_result.scalar() or 0

    if subscription_count > 0:
        logger.warning(
            f"Cannot delete connection with subscriptions: id={connection_id}, "
            f"subscription_count={subscription_count}"
        )
        raise ValidationError(
            f"Cannot delete connection with {subscription_count} subscription(s). "
            "Please delete all subscriptions first."
        )

    # 5. Soft delete (set deleted_at)
    connection.deleted_at = datetime.now()
    logger.debug(f"Connection soft deleted: id={connection_id}")

    logger.info(f"Connection deleted successfully: id={connection_id}")
    return SuccessResponse(data=None)
