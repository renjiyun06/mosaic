"""Session management API endpoints"""

import logging
from datetime import datetime
from math import ceil

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from typing import Annotated, Optional

from ..schema.response import SuccessResponse, PaginatedData
from ..schema.session import CreateSessionRequest, SessionOut, SessionTopologyNode, SessionTopologyResponse, BatchArchiveResponse
from ..model import Session, Node, Mosaic, SessionRouting
from ..dep import get_db_session, get_current_user
from ..model.user import User
from ..exception import NotFoundError, PermissionError, ValidationError
from ..enum import SessionStatus

logger = logging.getLogger(__name__)

# Router configuration
router = APIRouter(prefix="/mosaics/{mosaic_id}/sessions", tags=["Session Management"])


# ==================== Type Aliases ====================

SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


# ==================== API Endpoints ====================

@router.post("", response_model=SuccessResponse[SessionOut])
async def create_session(
    mosaic_id: int,
    request: CreateSessionRequest,
    req: Request,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """Create a new session

    Business logic:
    1. Query mosaic and verify ownership
    2. Verify node exists in the specified mosaic
    3. Call RuntimeManager.create_session() to create runtime session (runtime layer creates DB record)
    4. Query the database record created by runtime layer
    5. Return created session

    Validation Rules:
    - Mosaic must exist and belong to current user
    - Node must exist in the mosaic (node_id from request body)
    - Mode must be PROGRAM or CHAT (BACKGROUND not allowed, validated in schema)

    Note:
        The runtime layer automatically creates the database Session record during
        session initialization. This API layer only queries and returns the created record.

    Raises:
        NotFoundError: If mosaic or node not found
        PermissionError: If mosaic doesn't belong to current user
        RuntimeException: If runtime session creation fails
    """
    logger.info(
        f"Creating session: mosaic_id={mosaic_id}, node_id={request.node_id}, "
        f"mode={request.mode}, user_id={current_user.id}"
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
        raise PermissionError("You do not have permission to create sessions in this mosaic")

    # 2. Verify node exists
    node_stmt = select(Node).where(
        Node.mosaic_id == mosaic_id,
        Node.node_id == request.node_id,
        Node.deleted_at.is_(None)
    )
    node_result = await session.execute(node_stmt)
    node = node_result.scalar_one_or_none()

    if not node:
        logger.warning(
            f"Node not found: mosaic_id={mosaic_id}, node_id={request.node_id}"
        )
        raise NotFoundError(f"Node '{request.node_id}' not found in this mosaic")

    # 3. Create runtime session and get session_id
    # Note: Runtime layer will create the database record during session initialization
    runtime_manager = req.app.state.runtime_manager
    session_id = await runtime_manager.create_session(
        node=node,
        mode=request.mode,
        model=request.model,
        token_threshold_enabled=node.config.get("token_threshold_enabled", False),
        token_threshold=node.config.get("token_threshold", 60000),
        inherit_threshold=node.config.get("inherit_threshold", True),
        timeout=10.0
    )

    logger.info(f"Runtime session created: session_id={session_id}")

    # 4. Query the database record created by runtime layer
    stmt = select(Session).where(Session.session_id == session_id)
    result = await session.execute(stmt)
    db_session = result.scalar_one()

    logger.info(
        f"Database session retrieved: id={db_session.id}, session_id={session_id}, "
        f"node_id={request.node_id}, mode={request.mode}"
    )

    # 5. Construct response
    session_out = SessionOut(
        id=db_session.id,
        session_id=db_session.session_id,
        user_id=db_session.user_id,
        mosaic_id=db_session.mosaic_id,
        node_id=db_session.node_id,
        mode=db_session.mode,
        model=db_session.model,
        status=db_session.status,
        topic=db_session.topic,
        message_count=db_session.message_count,
        total_input_tokens=db_session.total_input_tokens,
        total_output_tokens=db_session.total_output_tokens,
        total_cost_usd=db_session.total_cost_usd,
        created_at=db_session.created_at,
        updated_at=db_session.updated_at,
        last_activity_at=db_session.last_activity_at,
        closed_at=db_session.closed_at
    )

    return SuccessResponse(data=session_out)


@router.post("/{session_id}/close", response_model=SuccessResponse[SessionOut])
async def close_session(
    mosaic_id: int,
    session_id: str,
    req: Request,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """Close an active session

    Business logic:
    1. Query session and verify ownership
    2. Query node for runtime close operation
    3. Verify session is currently ACTIVE
    4. Update database status to CLOSED
    5. Call RuntimeManager.close_session() to close runtime session
    6. Return updated session

    Validation Rules:
    - Session must exist and belong to current user
    - Session must be in ACTIVE status (cannot close already closed/archived session)

    Raises:
        NotFoundError: If session or node not found
        PermissionError: If session doesn't belong to current user
        ValidationError: If session is not active
        RuntimeException: If runtime session close fails
    """
    logger.info(
        f"Closing session: mosaic_id={mosaic_id}, session_id={session_id}, "
        f"user_id={current_user.id}"
    )

    # 1. Query session and verify ownership
    stmt = select(Session).where(
        Session.session_id == session_id,
        Session.mosaic_id == mosaic_id,
        Session.user_id == current_user.id,
        Session.deleted_at.is_(None)
    )
    result = await session.execute(stmt)
    db_session = result.scalar_one_or_none()

    if not db_session:
        logger.warning(
            f"Session not found: session_id={session_id}, mosaic_id={mosaic_id}, "
            f"user_id={current_user.id}"
        )
        raise NotFoundError("Session not found")

    # 2. Query node for runtime operation
    node_stmt = select(Node).where(
        Node.mosaic_id == mosaic_id,
        Node.node_id == db_session.node_id,
        Node.deleted_at.is_(None)
    )
    node_result = await session.execute(node_stmt)
    node = node_result.scalar_one_or_none()

    if not node:
        logger.warning(
            f"Node not found: mosaic_id={mosaic_id}, node_id={db_session.node_id}"
        )
        raise NotFoundError(f"Node '{db_session.node_id}' not found")

    # 3. Verify session is ACTIVE
    if db_session.status != SessionStatus.ACTIVE:
        logger.warning(
            f"Cannot close non-active session: session_id={session_id}, "
            f"current_status={db_session.status}"
        )
        raise ValidationError(
            f"Cannot close session with status '{db_session.status}'. "
            "Only active sessions can be closed."
        )

    # 4. Close runtime session first (runtime layer handles its own DB updates)
    runtime_manager = req.app.state.runtime_manager
    await runtime_manager.close_session(
        node=node,
        session=db_session,
        timeout=10.0
    )

    logger.info(f"Runtime session closed successfully: session_id={session_id}")

    # 5. Update database status to CLOSED (final confirmation after runtime cleanup)
    db_session.status = SessionStatus.CLOSED
    db_session.closed_at = datetime.now()
    db_session.updated_at = datetime.now()
    await session.flush()

    logger.info(f"Database session status updated to CLOSED: session_id={session_id}")

    # 6. Construct response
    session_out = SessionOut(
        id=db_session.id,
        session_id=db_session.session_id,
        user_id=db_session.user_id,
        mosaic_id=db_session.mosaic_id,
        node_id=db_session.node_id,
        mode=db_session.mode,
        model=db_session.model,
        status=db_session.status,
        topic=db_session.topic,
        message_count=db_session.message_count,
        total_input_tokens=db_session.total_input_tokens,
        total_output_tokens=db_session.total_output_tokens,
        total_cost_usd=db_session.total_cost_usd,
        created_at=db_session.created_at,
        updated_at=db_session.updated_at,
        last_activity_at=db_session.last_activity_at,
        closed_at=db_session.closed_at
    )

    return SuccessResponse(data=session_out)


@router.post("/{session_id}/archive", response_model=SuccessResponse[SessionOut])
async def archive_session(
    mosaic_id: int,
    session_id: str,
    session: SessionDep,
    current_user: CurrentUserDep,
):
    """Archive a closed session

    Business logic:
    1. Query session and verify ownership
    2. Verify session is currently CLOSED
    3. Update status to ARCHIVED
    4. Update updated_at timestamp
    5. Return updated session

    Validation Rules:
    - Session must exist and belong to current user
    - Session must be in CLOSED status (archiving requires session to be closed first)

    Raises:
        NotFoundError: If session not found
        PermissionError: If session doesn't belong to current user
        ValidationError: If session is not closed
    """
    logger.info(
        f"Archiving session: mosaic_id={mosaic_id}, session_id={session_id}, "
        f"user_id={current_user.id}"
    )

    # 1. Query session and verify ownership
    stmt = select(Session).where(
        Session.session_id == session_id,
        Session.mosaic_id == mosaic_id,
        Session.user_id == current_user.id,
        Session.deleted_at.is_(None)
    )
    result = await session.execute(stmt)
    db_session = result.scalar_one_or_none()

    if not db_session:
        logger.warning(
            f"Session not found: session_id={session_id}, mosaic_id={mosaic_id}, "
            f"user_id={current_user.id}"
        )
        raise NotFoundError("Session not found")

    # 2. Verify session is CLOSED
    if db_session.status != SessionStatus.CLOSED:
        logger.warning(
            f"Cannot archive non-closed session: session_id={session_id}, "
            f"current_status={db_session.status}"
        )
        raise ValidationError(
            f"Cannot archive session with status '{db_session.status}'. "
            "Session must be closed before archiving."
        )

    # 3. Update status to ARCHIVED
    db_session.status = SessionStatus.ARCHIVED
    db_session.updated_at = datetime.now()

    logger.info(f"Session archived successfully: session_id={session_id}")

    # 4. Construct response
    session_out = SessionOut(
        id=db_session.id,
        session_id=db_session.session_id,
        user_id=db_session.user_id,
        mosaic_id=db_session.mosaic_id,
        node_id=db_session.node_id,
        mode=db_session.mode,
        model=db_session.model,
        status=db_session.status,
        topic=db_session.topic,
        message_count=db_session.message_count,
        total_input_tokens=db_session.total_input_tokens,
        total_output_tokens=db_session.total_output_tokens,
        total_cost_usd=db_session.total_cost_usd,
        created_at=db_session.created_at,
        updated_at=db_session.updated_at,
        last_activity_at=db_session.last_activity_at,
        closed_at=db_session.closed_at
    )

    return SuccessResponse(data=session_out)


@router.post("/batch-archive", response_model=SuccessResponse[BatchArchiveResponse])
async def batch_archive_sessions(
    mosaic_id: int,
    session: SessionDep,
    current_user: CurrentUserDep,
    node_id: Optional[str] = Query(None, description="Filter by node ID to archive only closed sessions of this node"),
):
    """Batch archive all closed sessions

    Business logic:
    1. Query all closed sessions for current user in mosaic
    2. Optionally filter by node_id if provided
    3. Update all sessions to ARCHIVED status
    4. Return count of archived sessions

    Query Parameters:
    - node_id: Optional node ID to only archive sessions from specific node

    Validation Rules:
    - Only CLOSED sessions will be archived (ACTIVE and ARCHIVED sessions are skipped)
    - User must own the mosaic

    Returns:
        BatchArchiveResponse with archived_count and failed_sessions list
    """
    logger.info(
        f"Batch archiving sessions: mosaic_id={mosaic_id}, node_id={node_id}, "
        f"user_id={current_user.id}"
    )

    # 1. Query all closed sessions
    stmt = select(Session).where(
        Session.mosaic_id == mosaic_id,
        Session.user_id == current_user.id,
        Session.status == SessionStatus.CLOSED,
        Session.deleted_at.is_(None)
    )

    # Apply node_id filter if provided
    if node_id:
        stmt = stmt.where(Session.node_id == node_id)

    result = await session.execute(stmt)
    closed_sessions = result.scalars().all()

    if not closed_sessions:
        logger.info(f"No closed sessions to archive: mosaic_id={mosaic_id}, node_id={node_id}")
        return SuccessResponse(data=BatchArchiveResponse(
            archived_count=0,
            failed_sessions=[]
        ))

    # 2. Update all sessions to ARCHIVED
    archived_count = 0
    failed_sessions = []
    now = datetime.now()

    for db_session in closed_sessions:
        try:
            db_session.status = SessionStatus.ARCHIVED
            db_session.updated_at = now
            archived_count += 1
        except Exception as e:
            logger.error(f"Failed to archive session {db_session.session_id}: {e}")
            failed_sessions.append(db_session.session_id)

    # 3. Commit changes
    try:
        await session.flush()
        logger.info(
            f"Batch archived {archived_count} sessions: mosaic_id={mosaic_id}, "
            f"node_id={node_id}, failed={len(failed_sessions)}"
        )
    except Exception as e:
        logger.error(f"Failed to commit batch archive: {e}")
        raise

    # 4. Construct response
    return SuccessResponse(data=BatchArchiveResponse(
        archived_count=archived_count,
        failed_sessions=failed_sessions
    ))


@router.get("", response_model=SuccessResponse[PaginatedData[SessionOut]])
async def list_sessions(
    mosaic_id: int,
    session: SessionDep,
    current_user: CurrentUserDep,
    node_id: Optional[str] = Query(None, description="Filter by node ID"),
    session_id: Optional[str] = Query(None, description="Filter by session ID"),
    status: Optional[SessionStatus] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=1000, description="Items per page"),
):
    """List sessions with filtering and pagination

    Business logic:
    1. Build query with filters:
       - mosaic_id (required, from path)
       - user_id (current user)
       - node_id (optional, exact match)
       - session_id (optional, exact match)
       - status (optional, exact match)
       - deleted_at IS NULL
    2. Count total matching records
    3. Apply pagination: ORDER BY last_activity_at DESC, LIMIT, OFFSET
    4. Return paginated results

    Query Parameters:
    - node_id: Filter by specific node ID (exact match, optional)
    - session_id: Filter by specific session ID (exact match, optional)
    - status: Filter by status (active/closed/archived, optional)
    - page: Page number (starts from 1)
    - page_size: Items per page (1-1000, default 20)

    Returns:
        Paginated list of sessions for specified mosaic, ordered by last_activity_at DESC (most recent first)

    Note: Returns empty list if no sessions found
    """
    logger.info(
        f"Listing sessions: mosaic_id={mosaic_id}, "
        f"user_id={current_user.id}, filters={{node_id={node_id}, session_id={session_id}, status={status}}}, "
        f"page={page}, page_size={page_size}"
    )

    # 1. Build base query with filters
    stmt = select(Session).where(
        Session.mosaic_id == mosaic_id,
        Session.user_id == current_user.id,
        Session.deleted_at.is_(None)
    )

    # Apply optional filters
    if node_id:
        stmt = stmt.where(Session.node_id == node_id)
    if session_id:
        stmt = stmt.where(Session.session_id == session_id)
    if status:
        stmt = stmt.where(Session.status == status)

    # 2. Count total records
    count_stmt = select(func.count()).select_from(stmt.subquery())
    count_result = await session.execute(count_stmt)
    total = count_result.scalar() or 0

    # 3. Calculate pagination
    total_pages = ceil(total / page_size) if total > 0 else 0
    offset = (page - 1) * page_size

    # 4. Apply sorting and pagination
    stmt = stmt.order_by(Session.last_activity_at.desc()).offset(offset).limit(page_size)

    # 5. Execute query
    result = await session.execute(stmt)
    sessions = result.scalars().all()

    logger.debug(
        f"Found {len(sessions)} sessions (total={total}, page={page}/{total_pages})"
    )

    # 6. Build response list with parent-child relationship info
    session_ids = [s.session_id for s in sessions]

    # 6.1 Batch query parent session mapping (remote -> local)
    parent_map = {}
    if session_ids:
        parent_map_stmt = select(
            SessionRouting.remote_session_id,
            SessionRouting.local_session_id
        ).where(
            SessionRouting.remote_session_id.in_(session_ids),
            SessionRouting.mosaic_id == mosaic_id,
            SessionRouting.deleted_at.is_(None)
        )
        parent_result = await session.execute(parent_map_stmt)
        parent_map = {row[0]: row[1] for row in parent_result.all()}

    # 6.2 Batch query child session count (local -> count(remote))
    child_count_map = {}
    if session_ids:
        child_count_stmt = select(
            SessionRouting.local_session_id,
            func.count(SessionRouting.remote_session_id)
        ).where(
            SessionRouting.local_session_id.in_(session_ids),
            SessionRouting.mosaic_id == mosaic_id,
            SessionRouting.deleted_at.is_(None)
        ).group_by(SessionRouting.local_session_id)
        child_result = await session.execute(child_count_stmt)
        child_count_map = {row[0]: row[1] for row in child_result.all()}

    # 6.3 Build response list with parent-child info
    session_list = [
        SessionOut(
            id=s.id,
            session_id=s.session_id,
            user_id=s.user_id,
            mosaic_id=s.mosaic_id,
            node_id=s.node_id,
            mode=s.mode,
            model=s.model,
            status=s.status,
            topic=s.topic,
            message_count=s.message_count,
            total_input_tokens=s.total_input_tokens,
            total_output_tokens=s.total_output_tokens,
            total_cost_usd=s.total_cost_usd,
            created_at=s.created_at,
            updated_at=s.updated_at,
            last_activity_at=s.last_activity_at,
            closed_at=s.closed_at,
            parent_session_id=parent_map.get(s.session_id),
            child_count=child_count_map.get(s.session_id, 0)
        )
        for s in sessions
    ]

    # 7. Construct paginated response
    paginated_data = PaginatedData(
        items=session_list,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )

    logger.info(
        f"Listed {len(session_list)} sessions: mosaic_id={mosaic_id}, "
        f"filters={{node_id={node_id}}}, page={page}/{total_pages}, total={total}"
    )

    return SuccessResponse(data=paginated_data)


# ==================== Helper Functions for Topology ====================


async def fetch_session_tree(
    session: AsyncSession,
    mosaic_id: int,
    root_session_id: str,
    max_depth: Optional[int] = None
) -> list[dict]:
    """Fetch session tree using recursive CTE

    Args:
        session: Database session
        mosaic_id: Mosaic ID to filter by
        root_session_id: Root session ID to start the tree from
        max_depth: Optional maximum depth to traverse (None for unlimited)

    Returns:
        List of session tree nodes with columns:
        - session_id: str
        - parent_id: Optional[str]
        - node_id: str
        - depth: int
        - status: str
        - created_at: datetime
        - closed_at: Optional[datetime]
    """
    # Build recursive CTE query
    cte_query = text("""
        WITH RECURSIVE session_tree AS (
            -- Base case: root session (has no parent in the tree)
            SELECT
                :root_session_id AS session_id,
                NULL AS parent_id,
                s.node_id AS node_id,
                0 AS depth,
                s.status AS status,
                s.created_at AS created_at,
                s.closed_at AS closed_at
            FROM sessions s
            WHERE s.session_id = :root_session_id
                AND s.mosaic_id = :mosaic_id
                AND s.deleted_at IS NULL

            UNION ALL

            -- Recursive case: find children through session_routings
            SELECT
                sr.remote_session_id AS session_id,
                sr.local_session_id AS parent_id,
                sr.remote_node_id AS node_id,
                st.depth + 1 AS depth,
                COALESCE(s.status, 'UNKNOWN') AS status,
                s.created_at AS created_at,
                s.closed_at AS closed_at
            FROM session_routings sr
            INNER JOIN session_tree st ON sr.local_session_id = st.session_id
            LEFT JOIN sessions s ON sr.remote_session_id = s.session_id
            WHERE sr.mosaic_id = :mosaic_id
                AND sr.deleted_at IS NULL
                AND (:max_depth IS NULL OR st.depth < :max_depth)
        )
        SELECT
            session_id,
            parent_id,
            node_id,
            depth,
            status,
            created_at,
            closed_at
        FROM session_tree
        ORDER BY depth, session_id
    """)

    # Execute query
    result = await session.execute(
        cte_query,
        {
            "root_session_id": root_session_id,
            "mosaic_id": mosaic_id,
            "max_depth": max_depth
        }
    )

    # Convert rows to dictionaries
    rows = result.mappings().all()
    return [dict(row) for row in rows]


def build_tree_structure(
    nodes: list[dict],
    root_session_id: str
) -> Optional[SessionTopologyNode]:
    """Build tree structure from flat node list

    Args:
        nodes: Flat list of session nodes from fetch_session_tree()
        root_session_id: Session ID of the root node

    Returns:
        Root SessionTopologyNode with nested children, or None if root not found
    """
    if not nodes:
        return None

    # Create mapping from session_id to node data
    node_map = {node['session_id']: node for node in nodes}

    # Create mapping from session_id to SessionTopologyNode
    topology_map: dict[str, SessionTopologyNode] = {}

    # First pass: create all SessionTopologyNode objects
    for node in nodes:
        topology_map[node['session_id']] = SessionTopologyNode(
            session_id=node['session_id'],
            node_id=node['node_id'],
            status=node['status'].lower() if node['status'] else 'active',
            parent_session_id=node['parent_id'],
            children=[],
            depth=node['depth'],
            descendant_count=0,  # Will be calculated in second pass
            created_at=node['created_at'],
            closed_at=node['closed_at']
        )

    # Second pass: build parent-child relationships
    for node in nodes:
        session_id = node['session_id']
        parent_id = node['parent_id']

        if parent_id and parent_id in topology_map:
            # Add current node to parent's children
            topology_map[parent_id].children.append(topology_map[session_id])

    # Third pass: calculate descendant counts (bottom-up)
    def calculate_descendants(node: SessionTopologyNode) -> int:
        """Recursively calculate descendant count"""
        if not node.children:
            node.descendant_count = 0
            return 0

        total = len(node.children)
        for child in node.children:
            total += calculate_descendants(child)

        node.descendant_count = total
        return total

    # Get root node and calculate descendants
    root_node = topology_map.get(root_session_id)
    if root_node:
        calculate_descendants(root_node)

    return root_node


@router.get("/{session_id}/topology", response_model=SuccessResponse[SessionTopologyResponse])
async def get_session_topology(
    mosaic_id: int,
    session_id: str,
    session: SessionDep,
    current_user: CurrentUserDep,
    max_depth: Optional[int] = Query(None, ge=1, le=100, description="Maximum depth to traverse (optional)")
):
    """Get session topology tree starting from a root session

    Business logic:
    1. Verify root session exists and belongs to current user
    2. Use recursive CTE to fetch complete session tree from session_routing
    3. Build tree structure with parent-child relationships
    4. Calculate tree statistics (total nodes, max depth, descendant counts)
    5. Return tree structure with root node

    Query Parameters:
    - max_depth: Optional limit on tree traversal depth (1-100, default unlimited)

    Returns:
        Session topology tree with root session and all descendants

    Note:
        - Uses SQLite recursive CTE for efficient tree traversal
        - Tree is built from session_routing relationships (local -> remote)
        - Each node includes session info, status, and descendant count
        - Root session is the starting point (depth=0)

    Raises:
        NotFoundError: If root session not found
        PermissionError: If session doesn't belong to current user
    """
    logger.info(
        f"Fetching session topology: mosaic_id={mosaic_id}, session_id={session_id}, "
        f"user_id={current_user.id}, max_depth={max_depth}"
    )

    # 1. Verify root session exists and belongs to current user
    stmt = select(Session).where(
        Session.session_id == session_id,
        Session.mosaic_id == mosaic_id,
        Session.user_id == current_user.id,
        Session.deleted_at.is_(None)
    )
    result = await session.execute(stmt)
    root_session = result.scalar_one_or_none()

    if not root_session:
        logger.warning(
            f"Root session not found or access denied: session_id={session_id}, "
            f"mosaic_id={mosaic_id}, user_id={current_user.id}"
        )
        raise NotFoundError("Session not found")

    # 2. Fetch session tree using recursive CTE
    tree_nodes = await fetch_session_tree(
        session=session,
        mosaic_id=mosaic_id,
        root_session_id=session_id,
        max_depth=max_depth
    )

    logger.debug(f"Fetched {len(tree_nodes)} nodes in session tree")

    # 3. Build tree structure
    root_topology = build_tree_structure(
        nodes=tree_nodes,
        root_session_id=session_id
    )

    if not root_topology:
        logger.error(f"Failed to build tree structure for session_id={session_id}")
        raise NotFoundError("Failed to build session tree")

    # 4. Calculate tree statistics
    total_nodes = len(tree_nodes)
    max_depth_actual = max((node['depth'] for node in tree_nodes), default=0)

    logger.info(
        f"Session topology built: session_id={session_id}, total_nodes={total_nodes}, "
        f"max_depth={max_depth_actual}"
    )

    # 5. Construct response
    topology_response = SessionTopologyResponse(
        root_session=root_topology,
        total_nodes=total_nodes,
        max_depth=max_depth_actual
    )

    return SuccessResponse(data=topology_response)
