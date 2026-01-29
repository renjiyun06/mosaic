"""PTY session management for individual terminal instances.

This module manages a single PTY (pseudo-terminal) process, handling:
- Process lifecycle (fork, exec, kill)
- Bidirectional I/O (read output, write input)
- Terminal sizing (TIOCSWINSZ ioctl)
- Message routing to WebSocket via UserMessageBroker
"""

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class PTYSession:
    """
    Manages a single PTY process for one terminal session.

    Architecture:
    - Runs in main event loop (FastAPI Loop A)
    - Uses asyncio.run_in_executor() for blocking PTY operations
    - Sends output to UserMessageBroker for WebSocket delivery

    Lifecycle:
    1. start() - Fork process, start shell, begin output reading
    2. write() - Send user input to PTY
    3. resize() - Update terminal dimensions
    4. stop() - Kill process, cleanup resources

    Threading:
    - All async methods run in main loop
    - Blocking I/O (os.read, os.write, pty.fork) run in executor threads
    - UserMessageBroker handles cross-thread message delivery

    Attributes:
        session_id: Unique session identifier
        workspace_path: Working directory for shell process
        user_broker: UserMessageBroker instance for sending messages
        user_id: User database ID for message routing
        master_fd: PTY master file descriptor (or None if not started)
        pid: Child process ID (or None if not started)
        running: Whether the PTY is currently active
        _read_task: Background task for reading PTY output
    """

    def __init__(
        self,
        session_id: str,
        workspace_path: str,
        user_broker,
        user_id: int
    ):
        """
        Initialize PTY session.

        Args:
            session_id: Unique session identifier
            workspace_path: Working directory for shell process
            user_broker: UserMessageBroker instance
            user_id: User database ID
        """
        self.session_id = session_id
        self.workspace_path = workspace_path
        self.user_broker = user_broker
        self.user_id = user_id

        # PTY state
        self.master_fd: Optional[int] = None
        self.pid: Optional[int] = None
        self.running = False

        # Background task for output reading
        self._read_task: Optional[asyncio.Task] = None

        logger.debug(f"PTYSession initialized: session_id={session_id}, path={workspace_path}")

    async def start(self) -> None:
        """
        Start the PTY process.

        Steps:
        1. Fork PTY process using pty.fork() (in executor)
        2. Child process: chdir to workspace_path, exec bash
        3. Parent process: save master_fd and pid
        4. Start background task for reading output
        5. Send terminal_status(started) to client

        Raises:
            RuntimeError: If already started
            OSError: If fork or exec fails

        Note:
            - Uses asyncio.get_event_loop().run_in_executor() for fork
            - Shell is started with: bash --norc --noprofile
            - Read task runs continuously until stop() is called
        """
        if self.running:
            raise RuntimeError(f"PTY already running: session_id={self.session_id}")

        logger.info(f"[PTYSession] Starting: session_id={self.session_id}")

        # Fork PTY in executor (blocking operation)
        loop = asyncio.get_event_loop()
        self.pid, self.master_fd = await loop.run_in_executor(None, self._fork_pty)

        # Mark as running
        self.running = True

        # Start background read task
        self._read_task = asyncio.create_task(self._read_output())

        # Send status to client
        self._send_status("started", "Terminal ready")

        logger.info(f"[PTYSession] Started: session_id={self.session_id}, pid={self.pid}")

    def _fork_pty(self) -> tuple[int, int]:
        """
        Fork PTY process (blocking operation, runs in executor).

        Returns:
            Tuple of (pid, master_fd)

        Raises:
            OSError: If fork or exec fails

        Child Process:
        - Changes directory to workspace_path
        - Executes: bash --norc --noprofile

        Parent Process:
        - Returns pid and master_fd

        Note:
            This method is SYNCHRONOUS and should only be called via run_in_executor.
        """
        import pty
        import os

        pid, master_fd = pty.fork()

        if pid == 0:  # Child process
            try:
                os.chdir(self.workspace_path)
            except Exception as e:
                logger.error(f"Failed to chdir to {self.workspace_path}: {e}")
                os._exit(1)

            os.execvp('bash', ['bash', '--norc', '--noprofile'])

        # Parent process
        return pid, master_fd

    async def _read_output(self) -> None:
        """
        Continuously read PTY output and send to client.

        This is a long-running background task that:
        1. Uses select() to check for available data (in executor)
        2. Reads from master_fd using os.read() (in executor)
        3. Sends output via UserMessageBroker
        4. Repeats until self.running becomes False

        Error Handling:
        - OSError on read: Terminate loop (process died)
        - Cancellation: Clean exit (stop() was called)

        Note:
            - Runs as asyncio.Task in main loop
            - Blocking I/O done via run_in_executor()
            - Sleeps briefly if no data available
        """
        logger.info(f"[PTYSession] Read task started: session_id={self.session_id}")

        while self.running:
            try:
                loop = asyncio.get_event_loop()
                output = await loop.run_in_executor(None, self._read_pty_nonblocking)

                if output:
                    self._send_output(output)
                else:
                    await asyncio.sleep(0.05)  # Brief sleep to avoid busy waiting

            except asyncio.CancelledError:
                logger.debug(f"[PTYSession] Read task cancelled: session_id={self.session_id}")
                raise
            except Exception as e:
                logger.error(f"[PTYSession] Read error: {e}")
                break

        logger.info(f"[PTYSession] Read task ended: session_id={self.session_id}")

    def _read_pty_nonblocking(self) -> Optional[str]:
        """
        Non-blocking read from PTY (runs in executor).

        Uses select() to check for data before reading.

        Returns:
            String data if available, None if no data

        Note:
            This method is SYNCHRONOUS and should only be called via run_in_executor.
        """
        import select
        import os

        if not self.master_fd:
            return None

        # Check if data is available (timeout 0.1 seconds)
        r, _, _ = select.select([self.master_fd], [], [], 0.1)

        if r:
            try:
                data = os.read(self.master_fd, 4096)
                return data.decode('utf-8', errors='replace')
            except OSError:
                return None  # Process may have died

        return None  # No data available

    async def write(self, data: str) -> None:
        """
        Write user input to PTY.

        Args:
            data: User input (keystrokes from xterm.js)

        Raises:
            RuntimeError: If PTY not started
            OSError: If write fails

        Note:
            Uses run_in_executor() for blocking os.write()
        """
        if not self.running or self.master_fd is None:
            raise RuntimeError(f"PTY not running: session_id={self.session_id}")

        logger.debug(
            f"[PTYSession] Writing input: session_id={self.session_id}, "
            f"data_length={len(data)}"
        )

        import os
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None, os.write, self.master_fd, data.encode('utf-8')
        )

    async def resize(self, cols: int, rows: int) -> None:
        """
        Resize terminal window.

        Args:
            cols: Terminal width (columns)
            rows: Terminal height (rows)

        Raises:
            RuntimeError: If PTY not started
            OSError: If ioctl fails

        Note:
            Uses TIOCSWINSZ ioctl via fcntl
            Runs in executor as it's a blocking operation
        """
        if not self.running or self.master_fd is None:
            raise RuntimeError(f"PTY not running: session_id={self.session_id}")

        logger.info(
            f"[PTYSession] Resizing: session_id={self.session_id}, "
            f"cols={cols}, rows={rows}"
        )

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._resize_pty, cols, rows)

    def _resize_pty(self, cols: int, rows: int) -> None:
        """
        Resize PTY using ioctl (runs in executor).

        Args:
            cols: Terminal width
            rows: Terminal height

        Note:
            This method is SYNCHRONOUS and should only be called via run_in_executor.
        """
        import fcntl
        import termios
        import struct

        # Pack window size: (rows, cols, xpixel, ypixel)
        winsize = struct.pack("HHHH", rows, cols, 0, 0)

        # Apply resize via ioctl
        fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsize)

    async def stop(self) -> None:
        """
        Stop the PTY process and cleanup resources.

        Steps:
        1. Set self.running = False to stop read loop
        2. Cancel read task and wait for it
        3. Kill child process (SIGTERM, then SIGKILL)
        4. Close master_fd
        5. Send terminal_status(stopped) to client

        Note:
            Safe to call multiple times (idempotent)
        """
        if not self.running:
            logger.debug(f"[PTYSession] Already stopped: session_id={self.session_id}")
            return

        logger.info(f"[PTYSession] Stopping: session_id={self.session_id}")

        self.running = False

        # 1. Cancel read task
        if self._read_task:
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass

        # 2. Kill process
        if self.pid:
            import os
            try:
                os.kill(self.pid, 15)  # SIGTERM (graceful)
                await asyncio.sleep(0.5)  # Wait for process to exit
                os.kill(self.pid, 9)   # SIGKILL (force)
            except ProcessLookupError:
                pass  # Process already exited

        # 3. Close file descriptor
        if self.master_fd:
            import os
            try:
                os.close(self.master_fd)
            except OSError:
                pass

        # 4. Send status
        self._send_status("stopped", "Terminal closed")

        logger.info(f"[PTYSession] Stopped: session_id={self.session_id}")

    def _send_output(self, data: str) -> None:
        """
        Send terminal output to client via UserMessageBroker.

        Args:
            data: Terminal output data

        Message Format:
        {
            "session_id": "...",
            "role": "system",
            "message_type": "terminal_output",
            "message_id": "term-out-{timestamp}",
            "sequence": 0,
            "timestamp": "2025-01-11T...",
            "payload": {"data": "output text"}
        }

        Note:
            - Uses user_broker.push_from_worker() for thread safety
            - Even though we're in main loop, this method may be called from executor context
            - sequence is set to 0 (RuntimeManager may adjust if needed)
        """
        import time

        self.user_broker.push_from_worker(self.user_id, {
            "session_id": self.session_id,
            "role": "system",
            "message_type": "terminal_output",
            "message_id": f"term-out-{int(time.time() * 1000)}",
            "sequence": 0,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "payload": {"data": data}
        })

    def _send_status(self, status: str, message: str) -> None:
        """
        Send terminal status message to client.

        Args:
            status: Status value ("started", "stopped", "error")
            message: Human-readable status message

        Message Format:
        {
            "session_id": "...",
            "role": "system",
            "message_type": "terminal_status",
            "message_id": "term-status-{timestamp}",
            "sequence": 0,
            "timestamp": "2025-01-11T...",
            "payload": {"status": "started", "message": "Terminal ready"}
        }
        """
        import time

        self.user_broker.push_from_worker(self.user_id, {
            "session_id": self.session_id,
            "role": "system",
            "message_type": "terminal_status",
            "message_id": f"term-status-{int(time.time() * 1000)}",
            "sequence": 0,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "payload": {"status": status, "message": message}
        })
