"""Subscription management API endpoints"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Annotated

from ..schema.response import SuccessResponse
from ..schema.subscription import (
    CreateSubscriptionRequest,
    UpdateSubscriptionRequest,
    SubscriptionOut,
)
from ..model import Subscription, Connection, Mosaic
from ..dep import get_db_session, get_current_user
from ..model.user import User
from ..exception import ConflictError, NotFoundError, PermissionError, ValidationError
from ..enum import MosaicStatus

logger = logging.getLogger(__name__)

# Router configuration
router = APIRouter(prefix="/mosaics/{mosaic_id}/subscriptions", tags=["Subscription Management"])


# ==================== Type Aliases ====================

SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


# ==================== API Endpoints ====================

@router.post("", response_model=SuccessResponse[SubscriptionOut])
async def create_subscription(
    mosaic_id: int,
    request: CreateSubscriptionRequest,
    req: Request,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """Create a new subscription on top of an existing connection

    Business logic:
    1. Query mosaic and verify ownership
    2. Verify mosaic is stopped (cannot modify running mosaic)
    3. Query connection by connection_id and verify:
       - Connection exists and belongs to the specified mosaic
       - Connection belongs to current user
    4. Extract source_node_id and target_node_id from connection (denormalization)
    5. Check if subscription already exists (unique constraint check)
    6. Create Subscription record
    7. Return created subscription

    Validation Rules:
    - Mosaic must exist and belong to current user
    - Mosaic must be stopped (cannot modify running mosaic)
    - connection_id must reference an existing connection in this mosaic
    - Unique constraint: (mosaic_id, source_node_id, target_node_id, event_type) for non-deleted records

    Raises:
        NotFoundError: If mosaic or connection not found
        PermissionError: If mosaic or connection doesn't belong to current user
        ValidationError: If mosaic is running
        ConflictError: If subscription already exists
    """
    logger.info(
        f"Creating subscription: mosaic_id={mosaic_id}, "
        f"connection_id={request.connection_id}, event_type={request.event_type}, "
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
        raise PermissionError("You do not have permission to create subscriptions in this mosaic")

    # 2. Verify mosaic is stopped
    runtime_manager = req.app.state.runtime_manager
    status = await runtime_manager.get_mosaic_status(mosaic)
    if status == MosaicStatus.RUNNING:
        logger.warning(f"Cannot modify running mosaic: id={mosaic_id}")
        raise ValidationError("Cannot create subscription in running mosaic. Please stop it first.")

    # 3. Query connection and verify ownership
    connection_stmt = select(Connection).where(
        Connection.id == request.connection_id,
        Connection.mosaic_id == mosaic_id,
        Connection.user_id == current_user.id,
        Connection.deleted_at.is_(None)
    )
    connection_result = await session.execute(connection_stmt)
    connection = connection_result.scalar_one_or_none()

    if not connection:
        logger.warning(
            f"Connection not found: id={request.connection_id}, mosaic_id={mosaic_id}, "
            f"user_id={current_user.id}"
        )
        raise NotFoundError(
            f"Connection with id {request.connection_id} not found in this mosaic"
        )

    # 4. Extract source_node_id and target_node_id from connection
    source_node_id = connection.source_node_id
    target_node_id = connection.target_node_id

    logger.debug(
        f"Connection found: id={connection.id}, "
        f"source={source_node_id}, target={target_node_id}"
    )

    # 5. Check for existing subscription
    existing_stmt = select(Subscription).where(
        Subscription.mosaic_id == mosaic_id,
        Subscription.source_node_id == source_node_id,
        Subscription.target_node_id == target_node_id,
        Subscription.event_type == request.event_type,
        Subscription.deleted_at.is_(None)
    )
    existing_result = await session.execute(existing_stmt)
    existing_subscription = existing_result.scalar_one_or_none()

    if existing_subscription:
        logger.warning(
            f"Subscription already exists: mosaic_id={mosaic_id}, "
            f"source={source_node_id}, target={target_node_id}, event_type={request.event_type}"
        )
        raise ConflictError(
            f"Subscription from '{source_node_id}' to '{target_node_id}' "
            f"for event type '{request.event_type}' already exists"
        )

    # 6. Create Subscription record
    subscription = Subscription(
        user_id=current_user.id,
        mosaic_id=mosaic_id,
        connection_id=request.connection_id,
        source_node_id=source_node_id,
        target_node_id=target_node_id,
        event_type=request.event_type,
        description=request.description
    )
    session.add(subscription)
    await session.flush()

    logger.info(
        f"Subscription created: id={subscription.id}, mosaic_id={mosaic_id}, "
        f"source={source_node_id}, target={target_node_id}, event_type={request.event_type}"
    )

    # 7. Construct response
    subscription_out = SubscriptionOut(
        id=subscription.id,
        user_id=subscription.user_id,
        mosaic_id=subscription.mosaic_id,
        connection_id=subscription.connection_id,
        source_node_id=subscription.source_node_id,
        target_node_id=subscription.target_node_id,
        event_type=subscription.event_type,
        description=subscription.description,
        created_at=subscription.created_at,
        updated_at=subscription.updated_at
    )

    return SuccessResponse(data=subscription_out)


@router.get("", response_model=SuccessResponse[list[SubscriptionOut]])
async def list_subscriptions(
    mosaic_id: int,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """List all subscriptions in a mosaic

    Business logic:
    1. Query all subscriptions WHERE mosaic_id=X AND user_id=Y AND deleted_at IS NULL
    2. Order by created_at DESC (newest first)
    3. Return list of subscriptions (empty list if none)

    Note: This endpoint does not verify if the mosaic exists. If mosaic doesn't exist
    or doesn't belong to user, it simply returns an empty list.

    Raises:
        (No exceptions raised - returns empty list if no subscriptions found)
    """
    logger.info(f"Listing subscriptions: mosaic_id={mosaic_id}, user_id={current_user.id}")

    # Query all subscriptions for this mosaic and user
    stmt = select(Subscription).where(
        Subscription.mosaic_id == mosaic_id,
        Subscription.user_id == current_user.id,
        Subscription.deleted_at.is_(None)
    ).order_by(Subscription.created_at.desc())

    result = await session.execute(stmt)
    subscriptions = result.scalars().all()

    logger.debug(
        f"Found {len(subscriptions)} subscriptions: mosaic_id={mosaic_id}, user_id={current_user.id}"
    )

    # Build response list
    subscription_list = [
        SubscriptionOut(
            id=sub.id,
            user_id=sub.user_id,
            mosaic_id=sub.mosaic_id,
            connection_id=sub.connection_id,
            source_node_id=sub.source_node_id,
            target_node_id=sub.target_node_id,
            event_type=sub.event_type,
            description=sub.description,
            created_at=sub.created_at,
            updated_at=sub.updated_at
        )
        for sub in subscriptions
    ]

    logger.info(
        f"Listed {len(subscription_list)} subscriptions: mosaic_id={mosaic_id}, user_id={current_user.id}"
    )
    return SuccessResponse(data=subscription_list)


@router.get("/{subscription_id}", response_model=SuccessResponse[SubscriptionOut])
async def get_subscription(
    mosaic_id: int,
    subscription_id: int,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """Get a specific subscription

    Business logic:
    1. Query subscription WHERE id=subscription_id AND mosaic_id=X AND user_id=Y AND deleted_at IS NULL
    2. If not found, raise NotFoundError
    3. Return subscription

    Raises:
        NotFoundError: If subscription not found or doesn't belong to specified mosaic/user
    """
    logger.info(
        f"Getting subscription: id={subscription_id}, mosaic_id={mosaic_id}, user_id={current_user.id}"
    )

    # Query subscription by ID with mosaic_id and user_id verification
    stmt = select(Subscription).where(
        Subscription.id == subscription_id,
        Subscription.mosaic_id == mosaic_id,
        Subscription.user_id == current_user.id,
        Subscription.deleted_at.is_(None)
    )
    result = await session.execute(stmt)
    subscription = result.scalar_one_or_none()

    if not subscription:
        logger.warning(
            f"Subscription not found: id={subscription_id}, mosaic_id={mosaic_id}, "
            f"user_id={current_user.id}"
        )
        raise NotFoundError("Subscription not found")

    # Construct response
    subscription_out = SubscriptionOut(
        id=subscription.id,
        user_id=subscription.user_id,
        mosaic_id=subscription.mosaic_id,
        connection_id=subscription.connection_id,
        source_node_id=subscription.source_node_id,
        target_node_id=subscription.target_node_id,
        event_type=subscription.event_type,
        description=subscription.description,
        created_at=subscription.created_at,
        updated_at=subscription.updated_at
    )

    logger.info(f"Subscription retrieved successfully: id={subscription_id}")
    return SuccessResponse(data=subscription_out)


@router.patch("/{subscription_id}", response_model=SuccessResponse[SubscriptionOut])
async def update_subscription(
    mosaic_id: int,
    subscription_id: int,
    request: UpdateSubscriptionRequest,
    req: Request,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """Update a subscription

    Business logic:
    1. Validate request: description must be provided
    2. Query mosaic and verify ownership
    3. Verify mosaic is stopped (cannot modify running mosaic)
    4. Query subscription and verify ownership
    5. Update description field
    6. Update updated_at timestamp
    7. Return updated subscription

    Note: Only description can be updated. Core fields (connection_id, source_node_id,
    target_node_id, event_type) are immutable.

    Validation Rules:
    - description field must be provided for update
    - Mosaic must be stopped (cannot modify running mosaic)
    - Core fields are immutable

    Raises:
        ValidationError: If no field provided for update or mosaic is running
        NotFoundError: If mosaic or subscription not found
        PermissionError: If mosaic or subscription doesn't belong to current user
    """
    logger.info(
        f"Updating subscription: id={subscription_id}, mosaic_id={mosaic_id}, "
        f"user_id={current_user.id}"
    )

    # 1. Validate request: description must be provided
    if request.description is None:
        raise ValidationError("Description field must be provided for update")

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
        raise ValidationError("Cannot update subscription in running mosaic. Please stop it first.")

    # 4. Query subscription and verify ownership
    stmt = select(Subscription).where(
        Subscription.id == subscription_id,
        Subscription.mosaic_id == mosaic_id,
        Subscription.user_id == current_user.id,
        Subscription.deleted_at.is_(None)
    )
    result = await session.execute(stmt)
    subscription = result.scalar_one_or_none()

    if not subscription:
        logger.warning(
            f"Subscription not found: id={subscription_id}, mosaic_id={mosaic_id}, "
            f"user_id={current_user.id}"
        )
        raise NotFoundError("Subscription not found")

    # 5. Update description
    subscription.description = request.description
    logger.debug(f"Subscription description updated: id={subscription_id}")

    # 6. Update the updated_at timestamp
    subscription.updated_at = datetime.now()

    # 7. Construct response
    subscription_out = SubscriptionOut(
        id=subscription.id,
        user_id=subscription.user_id,
        mosaic_id=subscription.mosaic_id,
        connection_id=subscription.connection_id,
        source_node_id=subscription.source_node_id,
        target_node_id=subscription.target_node_id,
        event_type=subscription.event_type,
        description=subscription.description,
        created_at=subscription.created_at,
        updated_at=subscription.updated_at
    )

    logger.info(f"Subscription updated successfully: id={subscription_id}")
    return SuccessResponse(data=subscription_out)


@router.delete("/{subscription_id}", response_model=SuccessResponse[None])
async def delete_subscription(
    mosaic_id: int,
    subscription_id: int,
    req: Request,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """Delete a subscription (soft delete)

    Business logic:
    1. Query mosaic and verify ownership
    2. Verify mosaic is stopped (cannot modify running mosaic)
    3. Query subscription and verify ownership
    4. Set deleted_at = datetime.now() (soft delete)
    5. Commit and return success

    Note:
    - This is a soft delete operation (sets deleted_at timestamp)
    - The record remains in database but is excluded from queries
    - Deleted subscriptions don't count toward unique constraint

    Raises:
        NotFoundError: If mosaic or subscription not found or already deleted
        PermissionError: If mosaic doesn't belong to current user
        ValidationError: If mosaic is running
    """
    logger.info(
        f"Deleting subscription: id={subscription_id}, mosaic_id={mosaic_id}, "
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
        raise PermissionError("You do not have permission to delete subscriptions in this mosaic")

    # 2. Verify mosaic is stopped
    runtime_manager = req.app.state.runtime_manager
    status = await runtime_manager.get_mosaic_status(mosaic)
    if status == MosaicStatus.RUNNING:
        logger.warning(f"Cannot modify running mosaic: id={mosaic_id}")
        raise ValidationError("Cannot delete subscription in running mosaic. Please stop it first.")

    # 3. Query subscription and verify ownership
    stmt = select(Subscription).where(
        Subscription.id == subscription_id,
        Subscription.mosaic_id == mosaic_id,
        Subscription.user_id == current_user.id,
        Subscription.deleted_at.is_(None)
    )
    result = await session.execute(stmt)
    subscription = result.scalar_one_or_none()

    if not subscription:
        logger.warning(
            f"Subscription not found: id={subscription_id}, mosaic_id={mosaic_id}, "
            f"user_id={current_user.id}"
        )
        raise NotFoundError("Subscription not found")

    # 4. Soft delete (set deleted_at)
    subscription.deleted_at = datetime.now()
    logger.debug(f"Subscription soft deleted: id={subscription_id}")

    logger.info(f"Subscription deleted successfully: id={subscription_id}")
    return SuccessResponse(data=None)
