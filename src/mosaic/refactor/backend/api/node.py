"""Node management API endpoints"""
from fastapi import APIRouter, HTTPException, status
from .deps import SessionDep, CurrentUser
from ..schemas.node import (
    NodeCreateRequest,
    NodeUpdateRequest,
    NodeResponse,
)
from ..services.node_service import NodeService
from ..exceptions import MosaicException
from ..logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/mosaics/{mosaic_id}/nodes", tags=["Node Management"])


@router.post(
    "",
    response_model=NodeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create node",
)
async def create_node(
    mosaic_id: int,
    request: NodeCreateRequest,
    session: SessionDep,
    current_user: CurrentUser,
) -> NodeResponse:
    """Create a new node in a mosaic instance

    Create a new node with configuration for the specified mosaic instance.

    - **mosaic_id**: Mosaic instance ID
    - **node_id**: Unique node identifier within mosaic (e.g., "scheduler_1")
    - **node_type**: Node type (scheduler, email, aggregator, agent, etc.)
    - **description**: Optional node description
    - **config**: Node configuration (JSON object)
    """
    try:
        logger.info(
            f"API: Creating node '{request.node_id}' in mosaic {mosaic_id} "
            f"for user {current_user.id}"
        )
        return await NodeService.create_node(
            session, mosaic_id, current_user.id, request
        )
    except MosaicException as e:
        logger.error(f"Failed to create node: {e.message}")
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get(
    "",
    response_model=list[NodeResponse],
    summary="List nodes",
)
async def list_nodes(
    mosaic_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> list[NodeResponse]:
    """Get all nodes for a mosaic instance

    Returns a list of all nodes in the specified mosaic instance.

    - **mosaic_id**: Mosaic instance ID
    """
    try:
        logger.debug(
            f"API: Listing nodes for mosaic {mosaic_id}, user {current_user.id}"
        )
        return await NodeService.list_nodes(session, mosaic_id, current_user.id)
    except MosaicException as e:
        logger.error(f"Failed to list nodes: {e.message}")
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get(
    "/{node_id}",
    response_model=NodeResponse,
    summary="Get node",
)
async def get_node(
    mosaic_id: int,
    node_id: str,
    session: SessionDep,
    current_user: CurrentUser,
) -> NodeResponse:
    """Get a single node

    Get detailed information about a specific node.

    - **mosaic_id**: Mosaic instance ID
    - **node_id**: Node identifier
    """
    try:
        logger.debug(
            f"API: Getting node '{node_id}' in mosaic {mosaic_id} "
            f"for user {current_user.id}"
        )
        return await NodeService.get_node(
            session, mosaic_id, node_id, current_user.id
        )
    except MosaicException as e:
        logger.error(f"Failed to get node: {e.message}")
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.put(
    "/{node_id}",
    response_model=NodeResponse,
    summary="Update node",
)
async def update_node(
    mosaic_id: int,
    node_id: str,
    request: NodeUpdateRequest,
    session: SessionDep,
    current_user: CurrentUser,
) -> NodeResponse:
    """Update a node

    Update description and/or configuration of a node.

    - **mosaic_id**: Mosaic instance ID
    - **node_id**: Node identifier
    - **description**: New description (optional)
    - **config**: New configuration (optional)
    """
    try:
        logger.info(
            f"API: Updating node '{node_id}' in mosaic {mosaic_id} "
            f"for user {current_user.id}"
        )
        return await NodeService.update_node(
            session, mosaic_id, node_id, current_user.id, request
        )
    except MosaicException as e:
        logger.error(f"Failed to update node: {e.message}")
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.delete(
    "/{node_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete node",
)
async def delete_node(
    mosaic_id: int,
    node_id: str,
    session: SessionDep,
    current_user: CurrentUser,
) -> None:
    """Delete a node (soft delete)

    Soft delete a node. The node will be marked as deleted
    but not physically removed from the database.

    - **mosaic_id**: Mosaic instance ID
    - **node_id**: Node identifier
    """
    try:
        logger.info(
            f"API: Deleting node '{node_id}' in mosaic {mosaic_id} "
            f"for user {current_user.id}"
        )
        await NodeService.delete_node(session, mosaic_id, node_id, current_user.id)
    except MosaicException as e:
        logger.error(f"Failed to delete node: {e.message}")
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post(
    "/{node_id}/start",
    response_model=NodeResponse,
    summary="Start node",
)
async def start_node(
    mosaic_id: int,
    node_id: str,
    session: SessionDep,
    current_user: CurrentUser,
) -> NodeResponse:
    """Start a node (runtime operation)

    Start the node process. This is a runtime operation that does not
    modify the database model.

    - **mosaic_id**: Mosaic instance ID
    - **node_id**: Node identifier
    """
    try:
        logger.info(
            f"API: Starting node '{node_id}' in mosaic {mosaic_id} "
            f"for user {current_user.id}"
        )
        return await NodeService.start_node(
            session, mosaic_id, node_id, current_user.id
        )
    except MosaicException as e:
        logger.error(f"Failed to start node: {e.message}")
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post(
    "/{node_id}/stop",
    response_model=NodeResponse,
    summary="Stop node",
)
async def stop_node(
    mosaic_id: int,
    node_id: str,
    session: SessionDep,
    current_user: CurrentUser,
) -> NodeResponse:
    """Stop a node (runtime operation)

    Stop the node process. This is a runtime operation that does not
    modify the database model.

    - **mosaic_id**: Mosaic instance ID
    - **node_id**: Node identifier
    """
    try:
        logger.info(
            f"API: Stopping node '{node_id}' in mosaic {mosaic_id} "
            f"for user {current_user.id}"
        )
        return await NodeService.stop_node(
            session, mosaic_id, node_id, current_user.id
        )
    except MosaicException as e:
        logger.error(f"Failed to stop node: {e.message}")
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post(
    "/{node_id}/restart",
    response_model=NodeResponse,
    summary="Restart node",
)
async def restart_node(
    mosaic_id: int,
    node_id: str,
    session: SessionDep,
    current_user: CurrentUser,
) -> NodeResponse:
    """Restart a node (runtime operation)

    Restart the node process. This is a runtime operation that does not
    modify the database model.

    - **mosaic_id**: Mosaic instance ID
    - **node_id**: Node identifier
    """
    try:
        logger.info(
            f"API: Restarting node '{node_id}' in mosaic {mosaic_id} "
            f"for user {current_user.id}"
        )
        return await NodeService.restart_node(
            session, mosaic_id, node_id, current_user.id
        )
    except MosaicException as e:
        logger.error(f"Failed to restart node: {e.message}")
        raise HTTPException(status_code=e.status_code, detail=e.message)
