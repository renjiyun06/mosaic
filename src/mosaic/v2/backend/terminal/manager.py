"""Terminal manager for coordinating all terminal sessions.

This module provides centralized management of PTY sessions, handling:
- Session lifecycle (creation, tracking, cleanup)
- Workspace path resolution
- Global session registry
"""

import logging
from typing import Dict, Optional
from .pty_session import PTYSession

logger = logging.getLogger(__name__)


class TerminalManager:
    """
    Global manager for all terminal sessions.

    Architecture:
    - Runs in main event loop (FastAPI Loop A)
    - Maintains registry of active PTYSession instances
    - Coordinates with RuntimeManager for session lifecycle

    Lifecycle:
    - Created once during RuntimeManager initialization
    - Lives for the entire application lifetime
    - Accessible via RuntimeManager.terminal_manager

    Thread Safety:
    - All methods run in main loop (no locking needed)
    - PTYSession instances also run in main loop

    Attributes:
        user_broker: UserMessageBroker instance for message routing
        terminals: Registry of active terminal sessions (session_id → PTYSession)
    """

    def __init__(self, user_broker):
        """
        Initialize terminal manager.

        Args:
            user_broker: UserMessageBroker instance from RuntimeManager

        Note:
            This is called once during RuntimeManager.__init__()
        """
        self.user_broker = user_broker
        self.terminals: Dict[str, PTYSession] = {}

        logger.info("TerminalManager initialized")

    async def start_terminal(
        self,
        session_id: str,
        workspace_path: str,
        user_id: int
    ) -> None:
        """
        Start a new terminal session.

        Steps:
        1. Check if terminal already exists for this session_id
        2. Create PTYSession instance
        3. Start the PTY process
        4. Register in self.terminals

        Args:
            session_id: Unique session identifier
            workspace_path: Working directory for shell
            user_id: User database ID for message routing

        Raises:
            RuntimeError: If terminal already exists for this session
            OSError: If PTY creation fails

        Note:
            - Called from RuntimeManager.start_terminal()
            - Runs in main event loop
            - workspace_path should be validated before calling
        """
        # Idempotent handling: check if terminal already exists
        if session_id in self.terminals:
            existing = self.terminals[session_id]

            # If terminal is running, return success (idempotent)
            if existing.running:
                logger.info(
                    f"[TerminalManager] Terminal already running (idempotent): "
                    f"session_id={session_id}"
                )
                # Re-send status to let frontend know terminal is ready
                existing._send_status("started", "Terminal ready")
                return

            # Terminal exists but stopped, clean up before recreating
            logger.warning(
                f"[TerminalManager] Removing stopped terminal before recreating: "
                f"session_id={session_id}"
            )
            del self.terminals[session_id]

        logger.info(
            f"[TerminalManager] Starting terminal: session_id={session_id}, "
            f"workspace_path={workspace_path}"
        )

        # Create PTYSession
        pty_session = PTYSession(session_id, workspace_path, self.user_broker, user_id)

        # Start the PTY
        await pty_session.start()

        # Register
        self.terminals[session_id] = pty_session

        logger.info(f"[TerminalManager] Terminal started: session_id={session_id}")

    async def send_input(self, session_id: str, data: str) -> None:
        """
        Send user input to terminal session.

        Args:
            session_id: Target session identifier
            data: User input data (keystrokes)

        Raises:
            KeyError: If terminal session not found
            RuntimeError: If terminal not running

        Note:
            - Called from RuntimeManager.send_terminal_input()
            - Delegates to PTYSession.write()
        """
        if session_id not in self.terminals:
            raise KeyError(f"Terminal not found: session_id={session_id}")

        logger.debug(
            f"[TerminalManager] Sending input: session_id={session_id}, "
            f"data_length={len(data)}"
        )

        await self.terminals[session_id].write(data)

    async def resize_terminal(self, session_id: str, cols: int, rows: int) -> None:
        """
        Resize terminal window.

        Args:
            session_id: Target session identifier
            cols: Terminal width
            rows: Terminal height

        Raises:
            KeyError: If terminal session not found
            RuntimeError: If terminal not running

        Note:
            - Called from RuntimeManager.resize_terminal()
            - Delegates to PTYSession.resize()
        """
        if session_id not in self.terminals:
            raise KeyError(f"Terminal not found: session_id={session_id}")

        logger.info(
            f"[TerminalManager] Resizing terminal: session_id={session_id}, "
            f"cols={cols}, rows={rows}"
        )

        await self.terminals[session_id].resize(cols, rows)

    async def stop_terminal(self, session_id: str) -> None:
        """
        Stop and cleanup terminal session.

        Steps:
        1. Find terminal in registry
        2. Stop the PTY process
        3. Remove from registry

        Args:
            session_id: Target session identifier

        Note:
            - Safe to call if terminal doesn't exist (no-op)
            - Called from RuntimeManager.stop_terminal()
            - Should also be called during session cleanup
        """
        if session_id not in self.terminals:
            logger.debug(f"[TerminalManager] Terminal not found: session_id={session_id}")
            return

        logger.info(f"[TerminalManager] Stopping terminal: session_id={session_id}")

        # Stop PTY
        await self.terminals[session_id].stop()

        # Remove from registry
        del self.terminals[session_id]

        logger.info(f"[TerminalManager] Terminal stopped: session_id={session_id}")

    async def cleanup_all(self) -> None:
        """
        Stop all terminal sessions.

        This is called during RuntimeManager shutdown.

        Steps:
        1. Iterate through all active terminals
        2. Stop each terminal
        3. Clear registry

        Note:
            - Errors are logged but don't stop cleanup
            - Should be called from RuntimeManager.stop()
        """
        if not self.terminals:
            logger.debug("[TerminalManager] No terminals to cleanup")
            return

        logger.info(f"[TerminalManager] Cleaning up {len(self.terminals)} terminals")

        session_ids = list(self.terminals.keys())
        for session_id in session_ids:
            try:
                await self.stop_terminal(session_id)
            except Exception as e:
                logger.error(f"Error stopping terminal {session_id}: {e}")

        self.terminals.clear()

        logger.info("[TerminalManager] All terminals cleaned up")
