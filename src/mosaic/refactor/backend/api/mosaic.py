"""Mosaic management API endpoints"""
from fastapi import APIRouter, HTTPException, status
from .deps import SessionDep, CurrentUser
from ..schemas.mosaic import (
    MosaicCreate,
    MosaicUpdate,
    MosaicResponse,
)
from ..schemas.topology import TopologyResponse
from ..services.mosaic_service import MosaicService
from ..exceptions import MosaicException
from ..logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/mosaics", tags=["Mosaic Management"])


@router.post(
    "",
    response_model=MosaicResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create mosaic instance",
)
async def create_mosaic(
    request: MosaicCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> MosaicResponse:
    """Create a new mosaic instance

    Create a new mosaic instance for the current user.

    - **name**: Mosaic instance name (1-100 characters)
    - **description**: Optional description (max 500 characters)
    """
    try:
        logger.info(
            f"API: Creating mosaic '{request.name}' for user {current_user.id}"
        )
        return await MosaicService.create_mosaic(session, current_user.id, request)
    except MosaicException as e:
        logger.error(f"Failed to create mosaic: {e.message}")
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get(
    "",
    response_model=list[MosaicResponse],
    summary="List mosaic instances",
)
async def list_mosaics(
    session: SessionDep,
    current_user: CurrentUser,
) -> list[MosaicResponse]:
    """Get all mosaic instances for the current user

    Returns a list of all mosaic instances owned by the current user.
    """
    try:
        logger.debug(f"API: Listing mosaics for user {current_user.id}")
        return await MosaicService.list_mosaics(session, current_user.id)
    except MosaicException as e:
        logger.error(f"Failed to list mosaics: {e.message}")
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get(
    "/{mosaic_id}",
    response_model=MosaicResponse,
    summary="Get mosaic instance",
)
async def get_mosaic(
    mosaic_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> MosaicResponse:
    """Get a single mosaic instance

    Get detailed information about a specific mosaic instance.

    - **mosaic_id**: Mosaic instance ID
    """
    try:
        logger.debug(
            f"API: Getting mosaic {mosaic_id} for user {current_user.id}"
        )
        return await MosaicService.get_mosaic(session, mosaic_id, current_user.id)
    except MosaicException as e:
        logger.error(f"Failed to get mosaic: {e.message}")
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.put(
    "/{mosaic_id}",
    response_model=MosaicResponse,
    summary="Update mosaic instance",
)
async def update_mosaic(
    mosaic_id: int,
    request: MosaicUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> MosaicResponse:
    """Update a mosaic instance

    Update name and/or description of a mosaic instance.

    - **mosaic_id**: Mosaic instance ID
    - **name**: New name (optional)
    - **description**: New description (optional)
    """
    try:
        logger.info(
            f"API: Updating mosaic {mosaic_id} for user {current_user.id}"
        )
        return await MosaicService.update_mosaic(
            session, mosaic_id, current_user.id, request
        )
    except MosaicException as e:
        logger.error(f"Failed to update mosaic: {e.message}")
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.delete(
    "/{mosaic_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete mosaic instance",
)
async def delete_mosaic(
    mosaic_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> None:
    """Delete a mosaic instance (soft delete)

    Soft delete a mosaic instance. The instance will be marked as deleted
    but not physically removed from the database.

    - **mosaic_id**: Mosaic instance ID
    """
    try:
        logger.info(
            f"API: Deleting mosaic {mosaic_id} for user {current_user.id}"
        )
        await MosaicService.delete_mosaic(session, mosaic_id, current_user.id)
    except MosaicException as e:
        logger.error(f"Failed to delete mosaic: {e.message}")
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get(
    "/{mosaic_id}/topology",
    response_model=TopologyResponse,
    summary="Get mosaic topology",
)
async def get_topology(
    mosaic_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> TopologyResponse:
    """Get topology visualization data for a mosaic

    Returns nodes, connections, and subscriptions for topology visualization.

    - **mosaic_id**: Mosaic instance ID
    """
    try:
        logger.debug(
            f"API: Getting topology for mosaic {mosaic_id}, user {current_user.id}"
        )
        return await MosaicService.get_topology(session, mosaic_id, current_user.id)
    except MosaicException as e:
        logger.error(f"Failed to get topology: {e.message}")
        raise HTTPException(status_code=e.status_code, detail=e.message)


# ========== Runtime Management ==========


@router.post(
    "/{mosaic_id}/start",
    response_model=MosaicResponse,
    summary="Start mosaic instance",
)
async def start_mosaic(
    mosaic_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> MosaicResponse:
    """Start a mosaic instance in the runtime layer

    This starts the mosaic instance and any nodes with auto_start enabled.

    - **mosaic_id**: Mosaic instance ID
    """
    try:
        logger.info(
            f"API: Starting mosaic {mosaic_id} for user {current_user.id}"
        )
        return await MosaicService.start_mosaic(session, mosaic_id, current_user.id)
    except MosaicException as e:
        logger.error(f"Failed to start mosaic: {e.message}")
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post(
    "/{mosaic_id}/stop",
    response_model=MosaicResponse,
    summary="Stop mosaic instance",
)
async def stop_mosaic(
    mosaic_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> MosaicResponse:
    """Stop a mosaic instance in the runtime layer

    This stops the mosaic instance and all running nodes.

    - **mosaic_id**: Mosaic instance ID
    """
    try:
        logger.info(
            f"API: Stopping mosaic {mosaic_id} for user {current_user.id}"
        )
        return await MosaicService.stop_mosaic(session, mosaic_id, current_user.id)
    except MosaicException as e:
        logger.error(f"Failed to stop mosaic: {e.message}")
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post(
    "/{mosaic_id}/restart",
    response_model=MosaicResponse,
    summary="Restart mosaic instance",
)
async def restart_mosaic(
    mosaic_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> MosaicResponse:
    """Restart a mosaic instance in the runtime layer

    This restarts the mosaic instance (stop then start).

    - **mosaic_id**: Mosaic instance ID
    """
    try:
        logger.info(
            f"API: Restarting mosaic {mosaic_id} for user {current_user.id}"
        )
        return await MosaicService.restart_mosaic(session, mosaic_id, current_user.id)
    except MosaicException as e:
        logger.error(f"Failed to restart mosaic: {e.message}")
        raise HTTPException(status_code=e.status_code, detail=e.message)
