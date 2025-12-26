"""Node management service"""
from datetime import datetime
from pathlib import Path
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from ..models.node import Node
from ..models.mosaic import Mosaic
from ..schemas.node import (
    NodeCreateRequest,
    NodeUpdateRequest,
    NodeResponse,
)
from ..utils.query import get_active_query
from ..exceptions import NotFoundError, AuthorizationError, ValidationError, RuntimeOperationError
from ..config import get_instance_path
from ..logger import get_logger

logger = get_logger(__name__)


class NodeService:
    """Node management service"""

    @staticmethod
    def _create_node_directory(user_id: int, mosaic_id: int, node_db_id: int) -> None:
        """Create node directory in mosaic's directory

        Args:
            user_id: User ID
            mosaic_id: Mosaic ID
            node_db_id: Node database ID (primary key)

        Creates:
            {instance_path}/users/{user_id}/{mosaic_id}/{node_db_id}/
        """
        try:
            instance_path = get_instance_path()
            node_dir = instance_path / "users" / str(user_id) / str(mosaic_id) / str(node_db_id)
            node_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created node directory: {node_dir}")
        except Exception as e:
            logger.error(
                f"Failed to create node directory for node {node_db_id} "
                f"in mosaic {mosaic_id}, user {user_id}: {e}"
            )
            # Don't fail the node creation if directory creation fails
            # This is a filesystem operation that shouldn't block node creation

    @staticmethod
    def _check_node_directory_empty(user_id: int, mosaic_id: int, node_db_id: int) -> bool:
        """Check if node directory is empty

        Args:
            user_id: User ID
            mosaic_id: Mosaic ID
            node_db_id: Node database ID (primary key)

        Returns:
            True if directory is empty or does not exist, False if directory contains files
        """
        try:
            instance_path = get_instance_path()
            node_dir = instance_path / "users" / str(user_id) / str(mosaic_id) / str(node_db_id)

            # If directory doesn't exist, consider it empty
            if not node_dir.exists():
                return True

            # Check if directory has any contents
            return not any(node_dir.iterdir())
        except Exception as e:
            logger.error(
                f"Error checking node directory for node {node_db_id} "
                f"in mosaic {mosaic_id}, user {user_id}: {e}"
            )
            # On error, prevent deletion by returning False
            return False

    @staticmethod
    def _delete_node_directory(user_id: int, mosaic_id: int, node_db_id: int) -> None:
        """Delete node directory (only if empty)

        Args:
            user_id: User ID
            mosaic_id: Mosaic ID
            node_db_id: Node database ID (primary key)
        """
        try:
            instance_path = get_instance_path()
            node_dir = instance_path / "users" / str(user_id) / str(mosaic_id) / str(node_db_id)

            if node_dir.exists() and node_dir.is_dir():
                node_dir.rmdir()  # rmdir only removes empty directories
                logger.info(f"Deleted node directory: {node_dir}")
        except Exception as e:
            logger.error(
                f"Failed to delete node directory for node {node_db_id} "
                f"in mosaic {mosaic_id}, user {user_id}: {e}"
            )
            # Don't fail the node deletion if directory deletion fails
            # The node is already soft-deleted in database

    @staticmethod
    def _to_response(node: Node, runtime_status: str | None = None) -> NodeResponse:
        """Convert Node model to response schema

        Args:
            node: Node model instance
            runtime_status: Optional runtime status from RuntimeManager

        Returns:
            NodeResponse
        """
        return NodeResponse(
            id=node.id,
            user_id=node.user_id,
            mosaic_id=node.mosaic_id,
            node_id=node.node_id,
            node_type=node.node_type,
            description=node.description,
            config=node.config,
            auto_start=node.auto_start,
            created_at=node.created_at,
            updated_at=node.updated_at,
            status=runtime_status,
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
            AuthorizationError: User does not own the mosaic
        """
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

        return mosaic

    @staticmethod
    async def create_node(
        session: AsyncSession,
        mosaic_id: int,
        user_id: int,
        request: NodeCreateRequest,
    ) -> NodeResponse:
        """Create a new node

        Args:
            session: Database session
            mosaic_id: Mosaic ID
            user_id: User ID
            request: Node creation request

        Returns:
            Created node response

        Raises:
            NotFoundError: Mosaic not found
            AuthorizationError: User does not own the mosaic
            ValidationError: Node ID already exists in this mosaic
        """
        logger.info(
            f"Creating node '{request.node_id}' in mosaic {mosaic_id} "
            f"for user {user_id}"
        )

        # Verify mosaic ownership
        mosaic = await NodeService._verify_mosaic_ownership(session, mosaic_id, user_id)

        # Check node_id uniqueness within mosaic
        existing_node_query = get_active_query(Node).where(
            Node.mosaic_id == mosaic_id,
            Node.node_id == request.node_id,
        )
        existing_result = await session.execute(existing_node_query)
        existing_node = existing_result.scalar_one_or_none()

        if existing_node:
            logger.warning(
                f"Node ID '{request.node_id}' already exists in mosaic {mosaic_id}"
            )
            raise ValidationError(
                f"Node ID '{request.node_id}' already exists in this mosaic"
            )

        # Create node
        node = Node(
            user_id=mosaic.user_id,  # Inherit user_id from mosaic
            mosaic_id=mosaic_id,
            node_id=request.node_id,
            node_type=request.node_type,
            description=request.description,
            config=request.config,
            auto_start=request.auto_start,
        )

        session.add(node)

        try:
            await session.commit()
            await session.refresh(node)
        except IntegrityError as e:
            session.rollback()
            logger.warning(
                f"IntegrityError when creating node '{request.node_id}' "
                f"in mosaic {mosaic_id}: {str(e)}"
            )
            # Check if it's a duplicate node_id error
            if "nodes.mosaic_id, nodes.node_id" in str(e) or "UNIQUE constraint failed" in str(e):
                raise ValidationError(
                    f"Node ID '{request.node_id}' already exists in this mosaic"
                )
            # Re-raise if it's a different integrity error
            raise ValidationError(f"Failed to create node: {str(e)}")

        logger.info(f"Node created with ID: {node.id}")

        # Create node directory in filesystem
        NodeService._create_node_directory(user_id, mosaic_id, node.id)

        return NodeService._to_response(node)

    @staticmethod
    async def list_nodes(
        session: AsyncSession,
        mosaic_id: int,
        user_id: int,
    ) -> list[NodeResponse]:
        """Get all nodes for a mosaic

        Args:
            session: Database session
            mosaic_id: Mosaic ID
            user_id: User ID

        Returns:
            List of node responses

        Raises:
            NotFoundError: Mosaic not found
            AuthorizationError: User does not own the mosaic
        """
        from ..runtime.manager import RuntimeManager

        logger.debug(f"Fetching nodes for mosaic {mosaic_id}, user {user_id}")

        # Verify mosaic ownership
        await NodeService._verify_mosaic_ownership(session, mosaic_id, user_id)

        # Query nodes
        query = get_active_query(Node).where(Node.mosaic_id == mosaic_id)
        result = await session.execute(query)
        nodes = result.scalars().all()

        logger.debug(f"Found {len(nodes)} nodes")

        # Get runtime manager to fetch status
        runtime_manager = RuntimeManager.get_instance()

        # Convert to responses with real runtime status
        return [
            NodeService._to_response(
                node,
                runtime_status=runtime_manager.get_node_status(mosaic_id, node.node_id)
            )
            for node in nodes
        ]

    @staticmethod
    async def get_node(
        session: AsyncSession,
        mosaic_id: int,
        node_id: str,
        user_id: int,
    ) -> NodeResponse:
        """Get a single node

        Args:
            session: Database session
            mosaic_id: Mosaic ID
            node_id: Node ID (node_id field, not primary key)
            user_id: User ID

        Returns:
            Node response

        Raises:
            NotFoundError: Mosaic or node not found
            AuthorizationError: User does not own the mosaic
        """
        logger.debug(
            f"Fetching node '{node_id}' in mosaic {mosaic_id} for user {user_id}"
        )

        # Verify mosaic ownership
        await NodeService._verify_mosaic_ownership(session, mosaic_id, user_id)

        # Query node
        query = get_active_query(Node).where(
            Node.mosaic_id == mosaic_id,
            Node.node_id == node_id,
        )
        result = await session.execute(query)
        node = result.scalar_one_or_none()

        if not node:
            logger.warning(f"Node '{node_id}' not found in mosaic {mosaic_id}")
            raise NotFoundError("Node not found")

        return NodeService._to_response(node)

    @staticmethod
    async def update_node(
        session: AsyncSession,
        mosaic_id: int,
        node_id: str,
        user_id: int,
        request: NodeUpdateRequest,
    ) -> NodeResponse:
        """Update a node

        Args:
            session: Database session
            mosaic_id: Mosaic ID
            node_id: Node ID (node_id field, not primary key)
            user_id: User ID
            request: Node update request

        Returns:
            Updated node response

        Raises:
            NotFoundError: Mosaic or node not found
            AuthorizationError: User does not own the mosaic
            ValidationError: Node is currently running
        """
        from ..runtime.manager import RuntimeManager

        logger.info(
            f"Updating node '{node_id}' in mosaic {mosaic_id} for user {user_id}"
        )

        # Verify mosaic ownership
        await NodeService._verify_mosaic_ownership(session, mosaic_id, user_id)

        # Query node
        query = get_active_query(Node).where(
            Node.mosaic_id == mosaic_id,
            Node.node_id == node_id,
        )
        result = await session.execute(query)
        node = result.scalar_one_or_none()

        if not node:
            logger.warning(f"Node '{node_id}' not found in mosaic {mosaic_id}")
            raise NotFoundError("Node not found")

        # Check if node is running
        runtime_manager = RuntimeManager.get_instance()
        node_status = runtime_manager.get_node_status(mosaic_id, node_id)

        if node_status == "running":
            logger.warning(
                f"Cannot update node '{node_id}' in mosaic {mosaic_id}: node is running"
            )
            raise ValidationError(
                "Cannot update node while it is running. Please stop the node first."
            )

        # Update fields
        if request.description is not None:
            node.description = request.description
        if request.config is not None:
            node.config = request.config
        if request.auto_start is not None:
            node.auto_start = request.auto_start

        node.updated_at = datetime.now()

        session.add(node)
        await session.commit()
        await session.refresh(node)

        logger.info(f"Node '{node_id}' updated successfully")

        return NodeService._to_response(node)

    @staticmethod
    async def delete_node(
        session: AsyncSession,
        mosaic_id: int,
        node_id: str,
        user_id: int,
    ) -> None:
        """Delete a node (soft delete)

        Args:
            session: Database session
            mosaic_id: Mosaic ID
            node_id: Node ID (node_id field, not primary key)
            user_id: User ID

        Raises:
            NotFoundError: Mosaic or node not found
            AuthorizationError: User does not own the mosaic
            ValidationError: Node is currently running or directory is not empty
        """
        from ..runtime.manager import RuntimeManager
        from ..services.session_service import SessionService

        logger.info(
            f"Deleting node '{node_id}' in mosaic {mosaic_id} for user {user_id}"
        )

        # Verify mosaic ownership
        await NodeService._verify_mosaic_ownership(session, mosaic_id, user_id)

        # Query node
        query = get_active_query(Node).where(
            Node.mosaic_id == mosaic_id,
            Node.node_id == node_id,
        )
        result = await session.execute(query)
        node = result.scalar_one_or_none()

        if not node:
            logger.warning(f"Node '{node_id}' not found in mosaic {mosaic_id}")
            raise NotFoundError("Node not found")

        # Check if node is running
        runtime_manager = RuntimeManager.get_instance()
        node_status = runtime_manager.get_node_status(mosaic_id, node_id)

        if node_status == "running":
            logger.warning(
                f"Cannot delete node '{node_id}' in mosaic {mosaic_id}: node is running"
            )
            raise ValidationError(
                "Cannot delete node while it is running. Please stop the node first."
            )

        # Check if node directory is empty before deletion
        if not NodeService._check_node_directory_empty(user_id, mosaic_id, node.id):
            logger.warning(
                f"Cannot delete node '{node_id}' (ID: {node.id}): directory is not empty"
            )
            raise ValidationError(
                "Cannot delete node: node directory is not empty. "
                "Please remove all files from the node directory first."
            )

        # Cascade delete all sessions associated with this node
        await SessionService.delete_node_sessions(session, node.id)

        # Soft delete
        node.soft_delete()

        session.add(node)
        await session.commit()

        logger.info(f"Node '{node_id}' deleted successfully")

        # Delete node directory after successful database deletion
        NodeService._delete_node_directory(user_id, mosaic_id, node.id)

    @staticmethod
    async def start_node(
        session: AsyncSession,
        mosaic_id: int,
        node_id: str,
        user_id: int,
    ) -> NodeResponse:
        """Start a node (runtime operation)

        Args:
            session: Database session
            mosaic_id: Mosaic ID
            node_id: Node ID (node_id field, not primary key)
            user_id: User ID

        Returns:
            Node response with updated runtime status

        Raises:
            NotFoundError: Mosaic or node not found
            AuthorizationError: User does not own the mosaic
        """
        from ..runtime.manager import RuntimeManager

        logger.info(
            f"Starting node '{node_id}' in mosaic {mosaic_id} for user {user_id}"
        )

        # Verify mosaic ownership
        await NodeService._verify_mosaic_ownership(session, mosaic_id, user_id)

        # Query node
        query = get_active_query(Node).where(
            Node.mosaic_id == mosaic_id,
            Node.node_id == node_id,
        )
        result = await session.execute(query)
        node = result.scalar_one_or_none()

        if not node:
            logger.warning(f"Node '{node_id}' not found in mosaic {mosaic_id}")
            raise NotFoundError("Node not found")

        # Call runtime layer to start node
        runtime_manager = RuntimeManager.get_instance()

        try:
            await runtime_manager.start_node(mosaic_id, node_id)
        except ValueError as e:
            # Convert runtime ValueError to user-friendly error
            logger.warning(f"Runtime error starting node '{node_id}': {e}")
            raise RuntimeOperationError(
                f"无法启动节点: Mosaic 实例未运行，请先启动 Mosaic"
            )

        # Get runtime status
        runtime_status = runtime_manager.get_node_status(mosaic_id, node_id)

        logger.info(f"Node '{node_id}' started successfully")

        return NodeService._to_response(node, runtime_status)

    @staticmethod
    async def stop_node(
        session: AsyncSession,
        mosaic_id: int,
        node_id: str,
        user_id: int,
    ) -> NodeResponse:
        """Stop a node (runtime operation)

        Args:
            session: Database session
            mosaic_id: Mosaic ID
            node_id: Node ID (node_id field, not primary key)
            user_id: User ID

        Returns:
            Node response with updated runtime status

        Raises:
            NotFoundError: Mosaic or node not found
            AuthorizationError: User does not own the mosaic
        """
        from ..runtime.manager import RuntimeManager

        logger.info(
            f"Stopping node '{node_id}' in mosaic {mosaic_id} for user {user_id}"
        )

        # Verify mosaic ownership
        await NodeService._verify_mosaic_ownership(session, mosaic_id, user_id)

        # Query node
        query = get_active_query(Node).where(
            Node.mosaic_id == mosaic_id,
            Node.node_id == node_id,
        )
        result = await session.execute(query)
        node = result.scalar_one_or_none()

        if not node:
            logger.warning(f"Node '{node_id}' not found in mosaic {mosaic_id}")
            raise NotFoundError("Node not found")

        # Call runtime layer to stop node
        runtime_manager = RuntimeManager.get_instance()

        try:
            await runtime_manager.stop_node(mosaic_id, node_id)
        except ValueError as e:
            # Convert runtime ValueError to user-friendly error
            logger.warning(f"Runtime error stopping node '{node_id}': {e}")
            raise RuntimeOperationError(
                f"无法停止节点: Mosaic 实例未运行"
            )

        # Get runtime status
        runtime_status = runtime_manager.get_node_status(mosaic_id, node_id)

        logger.info(f"Node '{node_id}' stopped successfully")

        return NodeService._to_response(node, runtime_status)

    @staticmethod
    async def restart_node(
        session: AsyncSession,
        mosaic_id: int,
        node_id: str,
        user_id: int,
    ) -> NodeResponse:
        """Restart a node (runtime operation)

        Args:
            session: Database session
            mosaic_id: Mosaic ID
            node_id: Node ID (node_id field, not primary key)
            user_id: User ID

        Returns:
            Node response with updated runtime status

        Raises:
            NotFoundError: Mosaic or node not found
            AuthorizationError: User does not own the mosaic
        """
        from ..runtime.manager import RuntimeManager

        logger.info(
            f"Restarting node '{node_id}' in mosaic {mosaic_id} for user {user_id}"
        )

        # Verify mosaic ownership
        await NodeService._verify_mosaic_ownership(session, mosaic_id, user_id)

        # Query node
        query = get_active_query(Node).where(
            Node.mosaic_id == mosaic_id,
            Node.node_id == node_id,
        )
        result = await session.execute(query)
        node = result.scalar_one_or_none()

        if not node:
            logger.warning(f"Node '{node_id}' not found in mosaic {mosaic_id}")
            raise NotFoundError("Node not found")

        # Call runtime layer to restart node
        runtime_manager = RuntimeManager.get_instance()

        try:
            await runtime_manager.restart_node(mosaic_id, node_id)
        except ValueError as e:
            # Convert runtime ValueError to user-friendly error
            logger.warning(f"Runtime error restarting node '{node_id}': {e}")
            raise RuntimeOperationError(
                f"无法重启节点: Mosaic 实例未运行"
            )

        # Get runtime status
        runtime_status = runtime_manager.get_node_status(mosaic_id, node_id)

        logger.info(f"Node '{node_id}' restarted successfully")

        return NodeService._to_response(node, runtime_status)
