"""Subscription management API endpoints"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from ..database import get_session
from ..api.deps import get_current_user
from ..models import User
from ..schemas.subscription import (
    SubscriptionCreateRequest,
    SubscriptionUpdateRequest,
    SubscriptionResponse,
)
from ..services.subscription_service import SubscriptionService

router = APIRouter()


@router.post(
    "/mosaics/{mosaic_id}/subscriptions",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_subscription(
    mosaic_id: int,
    request: SubscriptionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Create a new subscription

    Creates an event subscription on top of an existing connection.
    A connection from source to target must exist before creating a subscription.

    Args:
        mosaic_id: Mosaic instance ID
        request: Subscription creation request
        current_user: Current authenticated user
        db: Database session

    Returns:
        Created subscription

    Raises:
        400: If validation fails or connection doesn't exist
        404: If mosaic or nodes not found
        403: If user doesn't have permission
    """
    subscription = await SubscriptionService.create_subscription(
        db, current_user.id, mosaic_id, request
    )
    return subscription


@router.get(
    "/mosaics/{mosaic_id}/subscriptions", response_model=List[SubscriptionResponse]
)
async def list_subscriptions(
    mosaic_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """List all subscriptions in a mosaic

    Args:
        mosaic_id: Mosaic instance ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        List of subscriptions

    Raises:
        404: If mosaic not found
        403: If user doesn't have permission
    """
    subscriptions = await SubscriptionService.list_subscriptions(
        db, current_user.id, mosaic_id
    )
    return subscriptions


@router.get(
    "/mosaics/{mosaic_id}/subscriptions/{subscription_id}",
    response_model=SubscriptionResponse,
)
async def get_subscription(
    mosaic_id: int,
    subscription_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Get a specific subscription

    Args:
        mosaic_id: Mosaic instance ID
        subscription_id: Subscription ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        Subscription

    Raises:
        404: If subscription not found
        403: If user doesn't have permission
    """
    subscription = await SubscriptionService.get_subscription(
        db, current_user.id, mosaic_id, subscription_id
    )
    return subscription


@router.put(
    "/mosaics/{mosaic_id}/subscriptions/{subscription_id}",
    response_model=SubscriptionResponse,
)
async def update_subscription(
    mosaic_id: int,
    subscription_id: int,
    request: SubscriptionUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Update a subscription

    Only description can be updated. Core fields (source, target, event_type)
    cannot be changed.

    Args:
        mosaic_id: Mosaic instance ID
        subscription_id: Subscription ID
        request: Subscription update request
        current_user: Current authenticated user
        db: Database session

    Returns:
        Updated subscription

    Raises:
        404: If subscription not found
        403: If user doesn't have permission
    """
    subscription = await SubscriptionService.update_subscription(
        db, current_user.id, mosaic_id, subscription_id, request
    )
    return subscription


@router.delete(
    "/mosaics/{mosaic_id}/subscriptions/{subscription_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_subscription(
    mosaic_id: int,
    subscription_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Delete a subscription

    Performs soft delete of the subscription.

    Args:
        mosaic_id: Mosaic instance ID
        subscription_id: Subscription ID
        current_user: Current authenticated user
        db: Database session

    Raises:
        404: If subscription not found
        403: If user doesn't have permission
    """
    await SubscriptionService.delete_subscription(
        db, current_user.id, mosaic_id, subscription_id
    )
    return None
