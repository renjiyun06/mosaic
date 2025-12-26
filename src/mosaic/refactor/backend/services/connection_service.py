"""Connection management service"""
from datetime import datetime
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.connection import Connection
from ..models.mosaic import Mosaic
from ..models.node import Node
from ..schemas.connection import (
    ConnectionCreateRequest,
    ConnectionUpdateRequest,
    ConnectionResponse,
)
from ..utils.query import get_active_query
from ..exceptions import NotFoundError, AuthorizationError, ValidationError
from ..logger import get_logger

logger = get_logger(__name__)


class ConnectionService:
    """Connection management service"""

    @staticmethod
    async def _to_response(session: AsyncSession, connection: Connection) -> ConnectionResponse:
        """Convert Connection model to response schema

        Args:
            session: Database session
            connection: Connection model instance

        Returns:
            ConnectionResponse
        """
        # Fetch node_id strings from database IDs
        source_node_query = select(Node.node_id).where(Node.id == connection.source_node_id)
        target_node_query = select(Node.node_id).where(Node.id == connection.target_node_id)

        source_result = await session.execute(source_node_query)
        target_result = await session.execute(target_node_query)

        source_node_id = source_result.scalar_one()
        target_node_id = target_result.scalar_one()

        return ConnectionResponse(
            id=connection.id,
            user_id=connection.user_id,
            mosaic_id=connection.mosaic_id,
            source_node_id=source_node_id,  # Return node_id string for API
            target_node_id=target_node_id,  # Return node_id string for API
            session_alignment=connection.session_alignment,
            description=connection.description,
            created_at=connection.created_at,
            updated_at=connection.updated_at,
        )

    @staticmethod
    async def _verify_mosaic_ownership(
        session: AsyncSession,
        mosaic_id: int,
        user_id: int,
    ) -> Mosaic:
        """Verify that the mosaic exists and belongs to the user

        Args:
            session: Database session
            mosaic_id: Mosaic ID
            user_id: User ID

        Returns:
            Mosaic instance

        Raises:
            NotFoundError: Mosaic not found
            AuthorizationError: User does not own this mosaic
        """
        query = get_active_query(Mosaic).where(Mosaic.id == mosaic_id)
        result = await session.execute(query)
        mosaic = result.scalar_one_or_none()

        if not mosaic:
            raise NotFoundError(f"Mosaic with id {mosaic_id} not found")

        if mosaic.user_id != user_id:
            raise AuthorizationError("You do not have permission to access this mosaic")

        return mosaic

    @staticmethod
    async def _verify_node_exists(
        session: AsyncSession,
        mosaic_id: int,
        node_id: str,
    ) -> Node:
        """Verify that a node exists in the mosaic

        Args:
            session: Database session
            mosaic_id: Mosaic ID
            node_id: Node ID

        Returns:
            Node instance

        Raises:
            ValidationError: Node not found
        """
        query = get_active_query(Node).where(
            Node.mosaic_id == mosaic_id, Node.node_id == node_id
        )
        result = await session.execute(query)
        node = result.scalar_one_or_none()

        if not node:
            raise ValidationError(f"Node '{node_id}' not found in this mosaic")

        return node

    @staticmethod
    async def create_connection(
        session: AsyncSession,
        mosaic_id: int,
        user_id: int,
        request: ConnectionCreateRequest,
    ) -> ConnectionResponse:
        """Create a new connection

        Args:
            session: Database session
            mosaic_id: Mosaic ID
            user_id: User ID
            request: Connection creation request

        Returns:
            ConnectionResponse

        Raises:
            NotFoundError: Mosaic not found
            AuthorizationError: User does not own this mosaic
            ValidationError: Node not found or connection already exists
        """
        logger.info(
            f"Creating connection in mosaic {mosaic_id}: {request.source_node_id} -> {request.target_node_id}"
        )

        # Verify mosaic ownership
        await ConnectionService._verify_mosaic_ownership(session, mosaic_id, user_id)

        # Verify both nodes exist and get their database IDs
        source_node = await ConnectionService._verify_node_exists(session, mosaic_id, request.source_node_id)
        target_node = await ConnectionService._verify_node_exists(session, mosaic_id, request.target_node_id)

        # Check if connection already exists (use database IDs)
        existing_query = get_active_query(Connection).where(
            Connection.mosaic_id == mosaic_id,
            Connection.source_node_id == source_node.id,  # Use database ID
            Connection.target_node_id == target_node.id,  # Use database ID
        )
        existing_result = await session.execute(existing_query)
        existing_connection = existing_result.scalar_one_or_none()

        if existing_connection:
            raise ValidationError(
                f"Connection from '{request.source_node_id}' to '{request.target_node_id}' already exists"
            )

        # Create connection (use database IDs from node lookups)
        connection = Connection(
            user_id=user_id,
            mosaic_id=mosaic_id,
            source_node_id=source_node.id,  # Use database ID, not node_id string
            target_node_id=target_node.id,  # Use database ID, not node_id string
            session_alignment=request.session_alignment.value,
            description=request.description,
        )

        session.add(connection)
        await session.commit()
        await session.refresh(connection)

        logger.info(f"Connection created successfully with id {connection.id}")
        return await ConnectionService._to_response(session, connection)

    @staticmethod
    async def list_connections(
        session: AsyncSession,
        mosaic_id: int,
        user_id: int,
    ) -> list[ConnectionResponse]:
        """List all connections in a mosaic

        Args:
            session: Database session
            mosaic_id: Mosaic ID
            user_id: User ID

        Returns:
            List of ConnectionResponse

        Raises:
            NotFoundError: Mosaic not found
            AuthorizationError: User does not own this mosaic
        """
        logger.info(f"Listing connections for mosaic {mosaic_id}")

        # Verify mosaic ownership
        await ConnectionService._verify_mosaic_ownership(session, mosaic_id, user_id)

        # Get all connections
        query = get_active_query(Connection).where(Connection.mosaic_id == mosaic_id)
        result = await session.execute(query)
        connections = result.scalars().all()

        logger.info(f"Found {len(connections)} connections")
        # Convert all connections to responses (async)
        responses = []
        for conn in connections:
            response = await ConnectionService._to_response(session, conn)
            responses.append(response)
        return responses

    @staticmethod
    async def get_connection(
        session: AsyncSession,
        mosaic_id: int,
        connection_id: int,
        user_id: int,
    ) -> ConnectionResponse:
        """Get a specific connection

        Args:
            session: Database session
            mosaic_id: Mosaic ID
            connection_id: Connection ID
            user_id: User ID

        Returns:
            ConnectionResponse

        Raises:
            NotFoundError: Mosaic or connection not found
            AuthorizationError: User does not own this mosaic
        """
        logger.info(f"Getting connection {connection_id} in mosaic {mosaic_id}")

        # Verify mosaic ownership
        await ConnectionService._verify_mosaic_ownership(session, mosaic_id, user_id)

        # Get connection
        query = get_active_query(Connection).where(
            Connection.mosaic_id == mosaic_id, Connection.id == connection_id
        )
        result = await session.execute(query)
        connection = result.scalar_one_or_none()

        if not connection:
            raise NotFoundError(f"Connection with id {connection_id} not found")

        return await ConnectionService._to_response(session, connection)

    @staticmethod
    async def update_connection(
        session: AsyncSession,
        mosaic_id: int,
        connection_id: int,
        user_id: int,
        request: ConnectionUpdateRequest,
    ) -> ConnectionResponse:
        """Update a connection

        Args:
            session: Database session
            mosaic_id: Mosaic ID
            connection_id: Connection ID
            user_id: User ID
            request: Connection update request

        Returns:
            ConnectionResponse

        Raises:
            NotFoundError: Mosaic or connection not found
            AuthorizationError: User does not own this mosaic
        """
        logger.info(f"Updating connection {connection_id} in mosaic {mosaic_id}")

        # Verify mosaic ownership
        await ConnectionService._verify_mosaic_ownership(session, mosaic_id, user_id)

        # Get connection
        query = get_active_query(Connection).where(
            Connection.mosaic_id == mosaic_id, Connection.id == connection_id
        )
        result = await session.execute(query)
        connection = result.scalar_one_or_none()

        if not connection:
            raise NotFoundError(f"Connection with id {connection_id} not found")

        # Update fields
        if request.session_alignment is not None:
            connection.session_alignment = request.session_alignment.value

        if request.description is not None:
            connection.description = request.description

        connection.updated_at = datetime.now()

        session.add(connection)
        await session.commit()
        await session.refresh(connection)

        logger.info(f"Connection {connection_id} updated successfully")
        return await ConnectionService._to_response(session, connection)

    @staticmethod
    async def delete_connection(
        session: AsyncSession,
        mosaic_id: int,
        connection_id: int,
        user_id: int,
    ) -> None:
        """Delete a connection (soft delete)

        Args:
            session: Database session
            mosaic_id: Mosaic ID
            connection_id: Connection ID
            user_id: User ID

        Raises:
            NotFoundError: Mosaic or connection not found
            AuthorizationError: User does not own this mosaic
        """
        logger.info(f"Deleting connection {connection_id} in mosaic {mosaic_id}")

        # Verify mosaic ownership
        await ConnectionService._verify_mosaic_ownership(session, mosaic_id, user_id)

        # Get connection
        query = get_active_query(Connection).where(
            Connection.mosaic_id == mosaic_id, Connection.id == connection_id
        )
        result = await session.execute(query)
        connection = result.scalar_one_or_none()

        if not connection:
            raise NotFoundError(f"Connection with id {connection_id} not found")

        # Soft delete
        connection.deleted_at = datetime.now()
        session.add(connection)
        await session.commit()

        logger.info(f"Connection {connection_id} deleted successfully")
