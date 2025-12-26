"""Mosaic management service"""
from pathlib import Path
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.mosaic import Mosaic
from ..models.node import Node
from ..models.connection import Connection
from ..models.subscription import Subscription
from ..schemas.mosaic import (
    MosaicCreate,
    MosaicUpdate,
    MosaicResponse,
)
from ..schemas.topology import (
    TopologyResponse,
    TopologyNodeResponse,
    TopologyConnectionResponse,
    TopologySubscriptionResponse,
)
from ..config import get_instance_path
from ..utils.query import get_active_query
from ..exceptions import NotFoundError, AuthorizationError, ValidationError
from ..logger import get_logger

logger = get_logger(__name__)


class MosaicService:
    """Mosaic management service"""

    @staticmethod
    def _create_mosaic_directory(user_id: int, mosaic_id: int) -> None:
        """Create mosaic directory in user's directory

        Args:
            user_id: User ID
            mosaic_id: Mosaic ID

        Creates:
            {instance_path}/users/{user_id}/{mosaic_id}/
        """
        try:
            instance_path = get_instance_path()
            mosaic_dir = instance_path / "users" / str(user_id) / str(mosaic_id)
            mosaic_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created mosaic directory: {mosaic_dir}")
        except Exception as e:
            logger.error(
                f"Failed to create mosaic directory for mosaic {mosaic_id}, "
                f"user {user_id}: {e}"
            )
            # Don't fail the mosaic creation if directory creation fails
            # This is a filesystem operation that shouldn't block mosaic creation


    @staticmethod
    async def _calculate_node_count(mosaic_id: int, session: AsyncSession) -> int:
        """Calculate node count for a mosaic

        Args:
            mosaic_id: Mosaic ID
            session: Database session

        Returns:
            Node count (non-deleted nodes only)
        """
        # Use get_active_query to ensure we only count non-deleted nodes
        query = get_active_query(Node).where(Node.mosaic_id == mosaic_id)
        result = await session.execute(query)
        nodes = result.scalars().all()
        count = len(nodes)

        logger.debug(f"Node count for mosaic {mosaic_id}: {count} (node IDs: {[n.node_id for n in nodes]})")
        return count

    @staticmethod
    async def _to_response(mosaic: Mosaic, session: AsyncSession, runtime_status: str | None = None) -> MosaicResponse:
        """Convert Mosaic model to response schema

        Args:
            mosaic: Mosaic model instance
            session: Database session
            runtime_status: Optional runtime status from RuntimeManager

        Returns:
            MosaicResponse
        """
        return MosaicResponse(
            id=mosaic.id,
            user_id=mosaic.user_id,
            name=mosaic.name,
            description=mosaic.description,
            status=runtime_status,
            node_count=await MosaicService._calculate_node_count(mosaic.id, session),
            created_at=mosaic.created_at,
            updated_at=mosaic.updated_at,
        )

    @staticmethod
    async def create_mosaic(
        session: AsyncSession,
        user_id: int,
        request: MosaicCreate,
    ) -> MosaicResponse:
        """Create a new mosaic instance

        Args:
            session: Database session
            user_id: User ID
            request: Mosaic creation request

        Returns:
            Created mosaic response
        """
        logger.info(f"Creating mosaic '{request.name}' for user {user_id}")

        # Create mosaic
        mosaic = Mosaic(
            user_id=user_id,
            name=request.name,
            description=request.description,
        )

        session.add(mosaic)
        await session.commit()
        await session.refresh(mosaic)

        logger.info(f"Mosaic created with ID: {mosaic.id}")

        # Create mosaic directory in filesystem
        MosaicService._create_mosaic_directory(user_id, mosaic.id)

        # Get runtime manager to fetch status
        from ..runtime.manager import RuntimeManager
        runtime_manager = RuntimeManager.get_instance()

        return await MosaicService._to_response(
            mosaic,
            session,
            runtime_status=runtime_manager.get_mosaic_status(mosaic.id)
        )

    @staticmethod
    async def list_mosaics(
        session: AsyncSession,
        user_id: int,
    ) -> list[MosaicResponse]:
        """Get all mosaic instances for a user

        Args:
            session: Database session
            user_id: User ID

        Returns:
            List of mosaic responses
        """
        from ..runtime.manager import RuntimeManager

        logger.debug(f"Fetching mosaics for user {user_id}")

        query = get_active_query(Mosaic).where(Mosaic.user_id == user_id)
        result = await session.execute(query)
        mosaics = result.scalars().all()

        logger.debug(f"Found {len(mosaics)} mosaics")

        # Get runtime manager to fetch status
        runtime_manager = RuntimeManager.get_instance()

        # Convert to list to support async iteration
        responses = []
        for mosaic in mosaics:
            response = await MosaicService._to_response(
                mosaic,
                session,
                runtime_status=runtime_manager.get_mosaic_status(mosaic.id)
            )
            responses.append(response)
        return responses

    @staticmethod
    async def get_mosaic(
        session: AsyncSession,
        mosaic_id: int,
        user_id: int,
    ) -> MosaicResponse:
        """Get a single mosaic instance

        Args:
            session: Database session
            mosaic_id: Mosaic ID
            user_id: User ID

        Returns:
            Mosaic response

        Raises:
            NotFoundError: Mosaic not found
            AuthorizationError: User does not own the mosaic
        """
        from ..runtime.manager import RuntimeManager

        logger.debug(f"Fetching mosaic {mosaic_id} for user {user_id}")

        query = get_active_query(Mosaic).where(Mosaic.id == mosaic_id)
        result = await session.execute(query)
        mosaic = result.scalar_one_or_none()

        if not mosaic:
            logger.warning(f"Mosaic not found: {mosaic_id}")
            raise NotFoundError("Mosaic not found")

        if mosaic.user_id != user_id:
            logger.warning(
                f"User {user_id} attempted to access mosaic {mosaic_id} "
                f"owned by user {mosaic.user_id}"
            )
            raise AuthorizationError("Access denied")

        # Get runtime manager to fetch status
        runtime_manager = RuntimeManager.get_instance()

        return await MosaicService._to_response(
            mosaic,
            session,
            runtime_status=runtime_manager.get_mosaic_status(mosaic_id)
        )

    @staticmethod
    async def update_mosaic(
        session: AsyncSession,
        mosaic_id: int,
        user_id: int,
        request: MosaicUpdate,
    ) -> MosaicResponse:
        """Update a mosaic instance

        Args:
            session: Database session
            mosaic_id: Mosaic ID
            user_id: User ID
            request: Mosaic update request

        Returns:
            Updated mosaic response

        Raises:
            NotFoundError: Mosaic not found
            AuthorizationError: User does not own the mosaic
            ValidationError: Mosaic is currently running
        """
        from ..runtime.manager import RuntimeManager

        logger.info(f"Updating mosaic {mosaic_id} for user {user_id}")

        query = get_active_query(Mosaic).where(Mosaic.id == mosaic_id)
        result = await session.execute(query)
        mosaic = result.scalar_one_or_none()

        if not mosaic:
            logger.warning(f"Mosaic not found: {mosaic_id}")
            raise NotFoundError("Mosaic not found")

        if mosaic.user_id != user_id:
            logger.warning(
                f"User {user_id} attempted to update mosaic {mosaic_id} "
                f"owned by user {mosaic.user_id}"
            )
            raise AuthorizationError("Access denied")

        # Check if mosaic is running
        runtime_manager = RuntimeManager.get_instance()
        mosaic_status = runtime_manager.get_mosaic_status(mosaic_id)

        if mosaic_status == "running":
            logger.warning(
                f"Cannot update mosaic {mosaic_id}: mosaic is running"
            )
            raise ValidationError(
                "Cannot update mosaic while it is running. Please stop the mosaic first."
            )

        # Update fields
        if request.name is not None:
            mosaic.name = request.name
        if request.description is not None:
            mosaic.description = request.description

        from datetime import datetime
        mosaic.updated_at = datetime.now()

        session.add(mosaic)
        await session.commit()
        await session.refresh(mosaic)

        logger.info(f"Mosaic {mosaic_id} updated successfully")

        return await MosaicService._to_response(
            mosaic,
            session,
            runtime_status=runtime_manager.get_mosaic_status(mosaic_id)
        )

    @staticmethod
    async def delete_mosaic(
        session: AsyncSession,
        mosaic_id: int,
        user_id: int,
    ) -> None:
        """Delete a mosaic instance (soft delete)

        Args:
            session: Database session
            mosaic_id: Mosaic ID
            user_id: User ID

        Raises:
            NotFoundError: Mosaic not found
            AuthorizationError: User does not own the mosaic
            ValidationError: Mosaic is currently running
        """
        from ..runtime.manager import RuntimeManager

        logger.info(f"Deleting mosaic {mosaic_id} for user {user_id}")

        query = get_active_query(Mosaic).where(Mosaic.id == mosaic_id)
        result = await session.execute(query)
        mosaic = result.scalar_one_or_none()

        if not mosaic:
            logger.warning(f"Mosaic not found: {mosaic_id}")
            raise NotFoundError("Mosaic not found")

        if mosaic.user_id != user_id:
            logger.warning(
                f"User {user_id} attempted to delete mosaic {mosaic_id} "
                f"owned by user {mosaic.user_id}"
            )
            raise AuthorizationError("Access denied")

        # Check if mosaic is running
        runtime_manager = RuntimeManager.get_instance()
        mosaic_status = runtime_manager.get_mosaic_status(mosaic_id)

        if mosaic_status == "running":
            logger.warning(
                f"Cannot delete mosaic {mosaic_id}: mosaic is running"
            )
            raise ValidationError(
                "Cannot delete mosaic while it is running. Please stop the mosaic first."
            )

        # Check if mosaic has any nodes
        node_count = await MosaicService._calculate_node_count(mosaic_id, session)
        logger.info(f"Mosaic {mosaic_id} has {node_count} active node(s)")

        if node_count > 0:
            logger.warning(
                f"Cannot delete mosaic {mosaic_id}: mosaic has {node_count} node(s)"
            )
            raise ValidationError(
                f"Cannot delete mosaic with existing nodes. Please delete all {node_count} node(s) first."
            )

        # Soft delete
        mosaic.soft_delete()

        session.add(mosaic)
        await session.commit()

        logger.info(f"Mosaic {mosaic_id} deleted successfully")

    @staticmethod
    async def get_topology(
        session: AsyncSession,
        mosaic_id: int,
        user_id: int,
    ) -> TopologyResponse:
        """Get topology visualization data for a mosaic

        Args:
            session: Database session
            mosaic_id: Mosaic ID
            user_id: User ID

        Returns:
            Topology response with nodes, connections, and subscriptions

        Raises:
            NotFoundError: Mosaic not found
            AuthorizationError: User does not own the mosaic
        """
        logger.debug(f"Fetching topology for mosaic {mosaic_id}, user {user_id}")

        # Verify mosaic exists and user has access
        query = get_active_query(Mosaic).where(Mosaic.id == mosaic_id)
        result = await session.execute(query)
        mosaic = result.scalar_one_or_none()

        if not mosaic:
            logger.warning(f"Mosaic not found: {mosaic_id}")
            raise NotFoundError("Mosaic not found")

        if mosaic.user_id != user_id:
            logger.warning(
                f"User {user_id} attempted to access topology for mosaic {mosaic_id} "
                f"owned by user {mosaic.user_id}"
            )
            raise AuthorizationError("Access denied")

        # Fetch nodes
        nodes_query = get_active_query(Node).where(Node.mosaic_id == mosaic_id)
        nodes_result = await session.execute(nodes_query)
        nodes = nodes_result.scalars().all()

        # Fetch connections
        connections_query = get_active_query(Connection).where(
            Connection.mosaic_id == mosaic_id
        )
        connections_result = await session.execute(connections_query)
        connections = connections_result.scalars().all()

        # Fetch subscriptions
        subscriptions_query = get_active_query(Subscription).where(
            Subscription.mosaic_id == mosaic_id
        )
        subscriptions_result = await session.execute(subscriptions_query)
        subscriptions = subscriptions_result.scalars().all()

        logger.debug(
            f"Found {len(nodes)} nodes, {len(connections)} connections, "
            f"{len(subscriptions)} subscriptions"
        )

        # Build mapping: database_id -> node_id string
        id_to_node_id = {node.id: node.node_id for node in nodes}

        # Convert to response schemas
        topology = TopologyResponse(
            nodes=[
                TopologyNodeResponse(
                    id=node.node_id,
                    node_id=node.node_id,
                    type=node.node_type,
                    config=node.config,
                )
                for node in nodes
            ],
            connections=[
                TopologyConnectionResponse(
                    source_node_id=id_to_node_id[conn.source_node_id],
                    target_node_id=id_to_node_id[conn.target_node_id],
                    alignment=conn.session_alignment,
                )
                for conn in connections
            ],
            subscriptions=[
                TopologySubscriptionResponse(
                    source_node_id=id_to_node_id[sub.source_node_id],
                    target_node_id=id_to_node_id[sub.target_node_id],
                    event_type=sub.event_type,
                )
                for sub in subscriptions
            ],
        )

        return topology

    # ========== Runtime Management ==========

    @staticmethod
    async def start_mosaic(
        session: AsyncSession,
        mosaic_id: int,
        user_id: int,
    ) -> MosaicResponse:
        """Start a mosaic instance in the runtime layer

        Args:
            session: Database session
            mosaic_id: Mosaic ID
            user_id: User ID

        Returns:
            Mosaic response with runtime_status

        Raises:
            NotFoundError: Mosaic not found
            AuthorizationError: User does not own the mosaic
        """
        from ..runtime.manager import RuntimeManager

        logger.info(f"Starting mosaic {mosaic_id} for user {user_id}")

        # Verify mosaic exists and user has access
        query = get_active_query(Mosaic).where(Mosaic.id == mosaic_id)
        result = await session.execute(query)
        mosaic = result.scalar_one_or_none()

        if not mosaic:
            logger.warning(f"Mosaic not found: {mosaic_id}")
            raise NotFoundError("Mosaic not found")

        if mosaic.user_id != user_id:
            logger.warning(
                f"User {user_id} attempted to start mosaic {mosaic_id} "
                f"owned by user {mosaic.user_id}"
            )
            raise AuthorizationError("Access denied")

        # Start in runtime layer
        runtime_manager = RuntimeManager.get_instance()
        await runtime_manager.start_mosaic(mosaic_id)

        # Get status
        runtime_status = runtime_manager.get_mosaic_status(mosaic_id)

        logger.info(f"Mosaic {mosaic_id} started successfully")

        return await MosaicService._to_response(mosaic, session, runtime_status)

    @staticmethod
    async def stop_mosaic(
        session: AsyncSession,
        mosaic_id: int,
        user_id: int,
    ) -> MosaicResponse:
        """Stop a mosaic instance in the runtime layer

        Args:
            session: Database session
            mosaic_id: Mosaic ID
            user_id: User ID

        Returns:
            Mosaic response with runtime_status

        Raises:
            NotFoundError: Mosaic not found
            AuthorizationError: User does not own the mosaic
        """
        from ..runtime.manager import RuntimeManager

        logger.info(f"Stopping mosaic {mosaic_id} for user {user_id}")

        # Verify mosaic exists and user has access
        query = get_active_query(Mosaic).where(Mosaic.id == mosaic_id)
        result = await session.execute(query)
        mosaic = result.scalar_one_or_none()

        if not mosaic:
            logger.warning(f"Mosaic not found: {mosaic_id}")
            raise NotFoundError("Mosaic not found")

        if mosaic.user_id != user_id:
            logger.warning(
                f"User {user_id} attempted to stop mosaic {mosaic_id} "
                f"owned by user {mosaic.user_id}"
            )
            raise AuthorizationError("Access denied")

        # Stop in runtime layer
        runtime_manager = RuntimeManager.get_instance()
        await runtime_manager.stop_mosaic(mosaic_id)

        # Get status
        runtime_status = runtime_manager.get_mosaic_status(mosaic_id)

        logger.info(f"Mosaic {mosaic_id} stopped successfully")

        return await MosaicService._to_response(mosaic, session, runtime_status)

    @staticmethod
    async def restart_mosaic(
        session: AsyncSession,
        mosaic_id: int,
        user_id: int,
    ) -> MosaicResponse:
        """Restart a mosaic instance in the runtime layer

        Args:
            session: Database session
            mosaic_id: Mosaic ID
            user_id: User ID

        Returns:
            Mosaic response with runtime_status

        Raises:
            NotFoundError: Mosaic not found
            AuthorizationError: User does not own the mosaic
        """
        from ..runtime.manager import RuntimeManager

        logger.info(f"Restarting mosaic {mosaic_id} for user {user_id}")

        # Verify mosaic exists and user has access
        query = get_active_query(Mosaic).where(Mosaic.id == mosaic_id)
        result = await session.execute(query)
        mosaic = result.scalar_one_or_none()

        if not mosaic:
            logger.warning(f"Mosaic not found: {mosaic_id}")
            raise NotFoundError("Mosaic not found")

        if mosaic.user_id != user_id:
            logger.warning(
                f"User {user_id} attempted to restart mosaic {mosaic_id} "
                f"owned by user {mosaic.user_id}"
            )
            raise AuthorizationError("Access denied")

        # Restart in runtime layer
        runtime_manager = RuntimeManager.get_instance()
        await runtime_manager.restart_mosaic(mosaic_id)

        # Get status
        runtime_status = runtime_manager.get_mosaic_status(mosaic_id)

        logger.info(f"Mosaic {mosaic_id} restarted successfully")

        return await MosaicService._to_response(mosaic, session, runtime_status)
