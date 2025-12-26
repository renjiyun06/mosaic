"""Workspace file management service"""
import mimetypes
from pathlib import Path
from datetime import datetime
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.node import Node
from ..schemas.workspace import (
    WorkspaceEntry,
    WorkspaceTreeResponse,
    WorkspaceFileResponse,
)
from ..exceptions import NotFoundError, AuthorizationError, ValidationError
from ..config import get_instance_path
from ..logger import get_logger

logger = get_logger(__name__)

# Maximum file size for preview (1 MB)
MAX_PREVIEW_SIZE = 1024 * 1024

# Blocked files/directories (security)
BLOCKED_PATTERNS = {'.env', '.git', 'id_rsa', 'id_ed25519', '*.key', '*.pem'}


class WorkspaceService:
    """Workspace file management service"""

    @staticmethod
    def _get_node_workspace(user_id: int, mosaic_id: int, node_db_id: int) -> Path:
        """Get node's workspace directory path

        Args:
            user_id: User ID
            mosaic_id: Mosaic ID
            node_db_id: Node database ID

        Returns:
            Workspace directory path
        """
        instance_path = get_instance_path()
        workspace = instance_path / "users" / str(user_id) / str(mosaic_id) / str(node_db_id)
        return workspace

    @staticmethod
    def _validate_path(workspace: Path, requested_path: str) -> Path:
        """Validate and resolve workspace path to prevent path traversal

        Args:
            workspace: Node's workspace root directory
            requested_path: User-requested relative path

        Returns:
            Resolved absolute path

        Raises:
            ValidationError: If path is invalid or outside workspace
        """
        # Handle empty path (workspace root)
        if not requested_path or requested_path == ".":
            return workspace

        # Resolve to absolute path
        try:
            full_path = (workspace / requested_path).resolve()
        except Exception as e:
            logger.warning(f"Invalid path resolution: {requested_path}, error: {e}")
            raise ValidationError(f"Invalid path: {requested_path}")

        # Check if path is within workspace
        try:
            full_path.relative_to(workspace)
        except ValueError:
            logger.warning(f"Path traversal attempt: {requested_path} -> {full_path}")
            raise ValidationError("Path outside workspace")

        return full_path

    @staticmethod
    def _is_blocked(path: Path) -> bool:
        """Check if file/directory is blocked for security reasons

        Args:
            path: File or directory path

        Returns:
            True if blocked, False otherwise
        """
        name = path.name.lower()

        # Check exact matches
        if name in BLOCKED_PATTERNS:
            return True

        # Check extensions for private keys
        if name.endswith(('.key', '.pem')):
            return True

        return False

    @staticmethod
    async def verify_node_access(
        db: AsyncSession,
        node_id: int,
        user_id: int
    ) -> Node:
        """Verify user has access to the node

        Args:
            db: Database session
            node_id: Node database ID
            user_id: User ID

        Returns:
            Node instance

        Raises:
            NotFoundError: If node not found
            AuthorizationError: If user doesn't own the node
        """
        # Get node
        result = await db.execute(
            select(Node)
            .where(Node.id == node_id)
            .where(Node.deleted_at.is_(None))
        )
        node = result.scalar_one_or_none()

        if not node:
            raise NotFoundError("Node not found")

        # Verify ownership
        if node.user_id != user_id:
            raise AuthorizationError("Access denied to this node")

        return node

    @staticmethod
    async def list_directory(
        db: AsyncSession,
        node_id: int,
        user_id: int,
        path: str = ""
    ) -> WorkspaceTreeResponse:
        """List directory contents in node's workspace

        Args:
            db: Database session
            node_id: Node database ID
            user_id: User ID
            path: Relative path from workspace root (default: root)

        Returns:
            Directory listing response

        Raises:
            NotFoundError: If node or directory not found
            AuthorizationError: If user doesn't have access
            ValidationError: If path is invalid
        """
        # Verify access
        node = await WorkspaceService.verify_node_access(db, node_id, user_id)

        # Get workspace directory
        workspace = WorkspaceService._get_node_workspace(
            user_id, node.mosaic_id, node.id
        )

        # Validate and resolve path
        target_path = WorkspaceService._validate_path(workspace, path)

        # Check if directory exists
        if not target_path.exists():
            raise NotFoundError(f"Directory not found: {path}")

        if not target_path.is_dir():
            raise ValidationError(f"Not a directory: {path}")

        # List directory contents
        entries: list[WorkspaceEntry] = []

        try:
            for item in sorted(target_path.iterdir(), key=lambda x: (not x.is_dir(), x.name)):
                # Skip blocked files
                if WorkspaceService._is_blocked(item):
                    continue

                # Get relative path from workspace
                relative_path = item.relative_to(workspace)

                # Get file info
                stat = item.stat()
                entry = WorkspaceEntry(
                    name=item.name,
                    path=str(relative_path),
                    type="directory" if item.is_dir() else "file",
                    size=stat.st_size if item.is_file() else 0,
                    modified_at=datetime.fromtimestamp(stat.st_mtime).isoformat()
                )
                entries.append(entry)

        except PermissionError:
            logger.error(f"Permission denied listing directory: {target_path}")
            raise ValidationError("Permission denied")

        return WorkspaceTreeResponse(
            entries=entries,
            current_path=path
        )

    @staticmethod
    async def read_file(
        db: AsyncSession,
        node_id: int,
        user_id: int,
        path: str
    ) -> WorkspaceFileResponse:
        """Read file content from node's workspace

        Args:
            db: Database session
            node_id: Node database ID
            user_id: User ID
            path: Relative file path from workspace root

        Returns:
            File content response

        Raises:
            NotFoundError: If node or file not found
            AuthorizationError: If user doesn't have access
            ValidationError: If path is invalid or file is blocked
        """
        # Verify access
        node = await WorkspaceService.verify_node_access(db, node_id, user_id)

        # Get workspace directory
        workspace = WorkspaceService._get_node_workspace(
            user_id, node.mosaic_id, node.id
        )

        # Validate and resolve path
        file_path = WorkspaceService._validate_path(workspace, path)

        # Check if file exists
        if not file_path.exists():
            raise NotFoundError(f"File not found: {path}")

        if not file_path.is_file():
            raise ValidationError(f"Not a file: {path}")

        # Check if blocked
        if WorkspaceService._is_blocked(file_path):
            raise ValidationError(f"Access denied: {path}")

        # Get file info
        stat = file_path.stat()
        file_size = stat.st_size

        # Detect MIME type
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if not mime_type:
            mime_type = "application/octet-stream"

        # Read file content
        is_truncated = False
        try:
            # Check if file is too large
            if file_size > MAX_PREVIEW_SIZE:
                # Read only first 1MB
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read(MAX_PREVIEW_SIZE)
                is_truncated = True
            else:
                # Read full file
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()

        except UnicodeDecodeError:
            # Binary file
            raise ValidationError("Cannot preview binary file")
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            raise ValidationError(f"Failed to read file: {str(e)}")

        return WorkspaceFileResponse(
            path=path,
            content=content,
            size=file_size,
            is_truncated=is_truncated,
            mime_type=mime_type
        )
