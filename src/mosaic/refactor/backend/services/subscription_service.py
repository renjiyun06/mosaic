"""Service for managing event subscriptions"""
from sqlmodel import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from typing import List
from datetime import datetime

from ..models import Subscription, Mosaic, Node, Connection
from ..schemas.subscription import (
    SubscriptionCreateRequest,
    SubscriptionUpdateRequest,
)
from ..exceptions import NotFoundError, ValidationError, AuthorizationError
from ..enums import EventType
from ..logger import get_logger

logger = get_logger(__name__)


class SubscriptionService:
    """Service for managing event subscriptions"""

    @staticmethod
    async def _to_response(db: AsyncSession, subscription: Subscription) -> Subscription:
        """
        Convert Subscription model to response-ready format.

        Fetches node_id strings for source and target nodes and replaces
        database IDs with node_id strings for API compatibility.

        Args:
            db: Database session
            subscription: Subscription model instance

        Returns:
            Subscription with node_id strings populated
        """
        # Fetch node_id strings from database IDs
        source_node_query = select(Node.node_id).where(Node.id == subscription.source_node_id)
        target_node_query = select(Node.node_id).where(Node.id == subscription.target_node_id)

        source_result = await db.execute(source_node_query)
        target_result = await db.execute(target_node_query)

        source_node_id_str = source_result.scalar_one()
        target_node_id_str = target_result.scalar_one()

        # Replace database IDs with node_id strings for API response
        # Note: This modifies the object in-place but doesn't commit to database
        subscription.source_node_id = source_node_id_str
        subscription.target_node_id = target_node_id_str

        return subscription

    @staticmethod
    async def create_subscription(
        db: AsyncSession, user_id: int, mosaic_id: int, request: SubscriptionCreateRequest
    ) -> Subscription:
        """Create a new subscription

        Args:
            db: Database session
            user_id: User ID
            mosaic_id: Mosaic instance ID
            request: Subscription creation request

        Returns:
            Created subscription

        Raises:
            NotFoundError: If mosaic, nodes, or connection not found
            ValidationError: If validation fails
            AuthorizationError: If user doesn't have permission
        """
        # Validate mosaic ownership
        mosaic = await db.get(Mosaic, mosaic_id)
        if not mosaic or mosaic.deleted_at is not None:
            raise NotFoundError("Mosaic not found")
        if mosaic.user_id != user_id:
            raise AuthorizationError(
                "You don't have permission to access this mosaic"
            )

        # Validate event type
        if request.event_type not in EventType.values():
            raise ValidationError(f"Invalid event type: {request.event_type}")

        # Validate source node exists
        result = await db.execute(
            select(Node).where(
                and_(
                    Node.mosaic_id == mosaic_id,
                    Node.node_id == request.source_node_id,
                    Node.deleted_at.is_(None),
                )
            )
        )
        source_node = result.scalar_one_or_none()
        if not source_node:
            raise NotFoundError(f"Source node not found: {request.source_node_id}")

        # Validate target node exists
        result = await db.execute(
            select(Node).where(
                and_(
                    Node.mosaic_id == mosaic_id,
                    Node.node_id == request.target_node_id,
                    Node.deleted_at.is_(None),
                )
            )
        )
        target_node = result.scalar_one_or_none()
        if not target_node:
            raise NotFoundError(f"Target node not found: {request.target_node_id}")

        # CRITICAL: Validate that a connection exists from source to target
        # Use database IDs from node lookups above
        result = await db.execute(
            select(Connection).where(
                and_(
                    Connection.mosaic_id == mosaic_id,
                    Connection.source_node_id == source_node.id,  # Use database ID
                    Connection.target_node_id == target_node.id,  # Use database ID
                    Connection.deleted_at.is_(None),
                )
            )
        )
        connection = result.scalar_one_or_none()
        if not connection:
            raise ValidationError(
                f"Cannot create subscription: No connection exists from "
                f"'{request.source_node_id}' to '{request.target_node_id}'. "
                f"Please create a connection first."
            )

        # Create subscription (use database IDs from node lookups)
        subscription = Subscription(
            user_id=user_id,
            mosaic_id=mosaic_id,
            source_node_id=source_node.id,  # Use database ID, not node_id string
            target_node_id=target_node.id,  # Use database ID, not node_id string
            event_type=request.event_type,
            description=request.description,
        )

        try:
            db.add(subscription)
            await db.commit()
            await db.refresh(subscription)
            logger.info(
                f"Created subscription: {request.source_node_id} -> "
                f"{request.target_node_id}, event: {request.event_type}"
            )
            return await SubscriptionService._to_response(db, subscription)
        except IntegrityError as e:
            await db.rollback()
            error_msg = str(e)
            # Check for duplicate subscription (works for both SQLite and PostgreSQL)
            if ("idx_active_subscriptions_unique" in error_msg or
                ("UNIQUE constraint failed" in error_msg and "subscriptions" in error_msg)):
                raise ValidationError(
                    f"Subscription already exists: '{request.source_node_id}' → "
                    f"'{request.target_node_id}' already subscribes to event type "
                    f"'{request.event_type}'"
                )
            raise

    @staticmethod
    async def list_subscriptions(
        db: AsyncSession, user_id: int, mosaic_id: int
    ) -> List[Subscription]:
        """List all subscriptions in a mosaic

        Args:
            db: Database session
            user_id: User ID
            mosaic_id: Mosaic instance ID

        Returns:
            List of subscriptions

        Raises:
            NotFoundError: If mosaic not found
            AuthorizationError: If user doesn't have permission
        """
        # Validate mosaic ownership
        mosaic = await db.get(Mosaic, mosaic_id)
        if not mosaic or mosaic.deleted_at is not None:
            raise NotFoundError("Mosaic not found")
        if mosaic.user_id != user_id:
            raise AuthorizationError(
                "You don't have permission to access this mosaic"
            )

        # Get all subscriptions
        result = await db.execute(
            select(Subscription)
            .where(
                and_(
                    Subscription.mosaic_id == mosaic_id,
                    Subscription.deleted_at.is_(None),
                )
            )
            .order_by(Subscription.created_at.desc())
        )
        subscriptions = result.scalars().all()

        # Convert all subscriptions to response format (async)
        responses = []
        for sub in subscriptions:
            response = await SubscriptionService._to_response(db, sub)
            responses.append(response)
        return responses

    @staticmethod
    async def get_subscription(
        db: AsyncSession, user_id: int, mosaic_id: int, subscription_id: int
    ) -> Subscription:
        """Get a specific subscription

        Args:
            db: Database session
            user_id: User ID
            mosaic_id: Mosaic instance ID
            subscription_id: Subscription ID

        Returns:
            Subscription

        Raises:
            NotFoundError: If subscription not found
            AuthorizationError: If user doesn't have permission
        """
        subscription = await db.get(Subscription, subscription_id)
        if not subscription or subscription.deleted_at is not None:
            raise NotFoundError("Subscription not found")
        if subscription.mosaic_id != mosaic_id or subscription.user_id != user_id:
            raise AuthorizationError(
                "You don't have permission to access this subscription"
            )

        return await SubscriptionService._to_response(db, subscription)

    @staticmethod
    async def update_subscription(
        db: AsyncSession,
        user_id: int,
        mosaic_id: int,
        subscription_id: int,
        request: SubscriptionUpdateRequest,
    ) -> Subscription:
        """Update a subscription (only description can be updated)

        Args:
            db: Database session
            user_id: User ID
            mosaic_id: Mosaic instance ID
            subscription_id: Subscription ID
            request: Subscription update request

        Returns:
            Updated subscription

        Raises:
            NotFoundError: If subscription not found
            AuthorizationError: If user doesn't have permission
        """
        # Get subscription (returns with node_id strings, but we need database IDs for update)
        subscription_with_strings = await SubscriptionService.get_subscription(
            db, user_id, mosaic_id, subscription_id
        )

        # Fetch the actual database record to update
        subscription = await db.get(Subscription, subscription_id)
        if not subscription:
            raise NotFoundError("Subscription not found")

        # Update fields
        if request.description is not None:
            subscription.description = request.description

        db.add(subscription)
        await db.commit()
        await db.refresh(subscription)
        logger.info(f"Updated subscription {subscription_id}")
        return await SubscriptionService._to_response(db, subscription)

    @staticmethod
    async def delete_subscription(
        db: AsyncSession, user_id: int, mosaic_id: int, subscription_id: int
    ) -> None:
        """Soft delete a subscription

        Args:
            db: Database session
            user_id: User ID
            mosaic_id: Mosaic instance ID
            subscription_id: Subscription ID

        Raises:
            NotFoundError: If subscription not found
            AuthorizationError: If user doesn't have permission
        """
        subscription = await SubscriptionService.get_subscription(
            db, user_id, mosaic_id, subscription_id
        )

        # Soft delete
        subscription.deleted_at = datetime.now()

        db.add(subscription)
        await db.commit()
        logger.info(
            f"Deleted subscription: {subscription.source_node_id} -> "
            f"{subscription.target_node_id}, event: {subscription.event_type}"
        )
