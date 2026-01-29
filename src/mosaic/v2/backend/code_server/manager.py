"""Code server instance manager - Single instance mode.

This module manages a single code-server process that serves all nodes.
Each node accesses the code-server via the ?folder= URL parameter.

Key features:
- Single code-server process for the entire application
- No workspace specified at startup (allows ?folder= parameter to work)
- Simple lifecycle: start on app startup, stop on app shutdown
- Health checking and automatic restart on failure
"""

import asyncio
import logging
import time
from pathlib import Path
from typing import Optional
from datetime import datetime
import subprocess

import aiohttp

logger = logging.getLogger(__name__)


class CodeServerManager:
    """Manages a single code-server process for all nodes

    This manager maintains one code-server instance that is started when
    the application starts and stopped when the application shuts down.

    Individual nodes access their workspaces via the ?folder= URL parameter,
    so no per-node instance management is needed.

    Usage:
        manager = CodeServerManager(
            host="127.0.0.1",
            port=20000,
            code_server_binary="code-server"
        )
        await manager.start()

        # Get URL for a specific workspace
        url = manager.get_url(workspace_path)

        # Cleanup on shutdown
        await manager.stop()
    """

    def __init__(self,
                 host: str = "127.0.0.1",
                 port: int = 20000,
                 code_server_binary: str = "code-server"):
        """Initialize CodeServerManager

        Args:
            host: Host address for binding and health checks (default: "127.0.0.1")
            port: Port number to bind code-server (default: 20000)
            code_server_binary: Path or name of code-server executable (default: "code-server")

        Notes:
        - Single port is used for all nodes
        - code_server_binary can be absolute path or command name in PATH
        - Instance runs without workspace (allows ?folder= parameter)
        """
        self.host = host
        self.port = port
        self.code_server_binary = code_server_binary

        # Single instance state
        self.process: Optional[subprocess.Popen] = None
        self.status: str = "stopped"  # 'stopped', 'starting', 'running', 'error'
        self.started_at: Optional[datetime] = None

        # Manager state
        self.running: bool = False
        self.lock: asyncio.Lock = asyncio.Lock()

        logger.info(
            f"CodeServerManager initialized: host={host}, "
            f"port={port}, binary={code_server_binary}"
        )


    async def start(self):
        """Start the code-server instance (called on application startup)

        Business logic:
        1. Check if already running (idempotent)
        2. Start code-server process without workspace
        3. Wait for process to be ready (health check)
        4. Update status to 'running'

        Notes:
        - This should be called in FastAPI lifespan startup
        - Should be idempotent (safe to call multiple times)
        - Process runs without workspace to allow ?folder= parameter
        """
        async with self.lock:
            if self.running:
                logger.warning("CodeServerManager already running")
                return

            logger.info("Starting CodeServerManager...")
            self.running = True
            self.status = "starting"

            try:
                # Start code-server process
                self.process = await self._start_process()
                self.started_at = datetime.now()

                # Wait for ready
                ready = await self._wait_for_ready(timeout=30)
                if not ready:
                    # Failed to start
                    self.status = "error"
                    if self.process:
                        self.process.terminate()
                        try:
                            self.process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            self.process.kill()
                            self.process.wait()
                        self.process = None
                    raise RuntimeError("Code-server failed to start within timeout")

                # Success
                self.status = "running"
                logger.info(
                    f"CodeServerManager started successfully: "
                    f"host={self.host}, port={self.port}, pid={self.process.pid}"
                )

            except Exception as e:
                self.status = "error"
                self.running = False
                logger.error(f"Failed to start CodeServerManager: {e}")
                raise


    async def stop(self):
        """Stop the code-server instance (called on application shutdown)

        Business logic:
        1. Check if running
        2. Terminate process gracefully (SIGTERM)
        3. Wait for process to exit (timeout: 5 seconds)
        4. Force kill if timeout
        5. Clear state

        Notes:
        - This should be called in FastAPI lifespan shutdown
        - Ensures clean termination of subprocess
        """
        async with self.lock:
            if not self.running:
                logger.warning("CodeServerManager not running")
                return

            logger.info("Stopping CodeServerManager...")
            self.running = False
            self.status = "stopped"

            if self.process:
                try:
                    # Terminate gracefully
                    self.process.terminate()
                    logger.info(f"Terminating code-server process: pid={self.process.pid}")

                    # Wait for process to exit
                    try:
                        self.process.wait(timeout=5)
                        logger.info("Code-server process terminated gracefully")
                    except subprocess.TimeoutExpired:
                        # Force kill if timeout
                        logger.warning("Code-server did not exit gracefully, force killing")
                        self.process.kill()
                        self.process.wait()
                        logger.info("Code-server process force killed")

                except Exception as e:
                    logger.error(f"Error stopping code-server process: {e}")

                finally:
                    self.process = None
                    self.started_at = None

            logger.info("CodeServerManager stopped successfully")


    def get_url(self, workspace_path: Path) -> str:
        """Build URL with folder parameter for a specific workspace

        Args:
            workspace_path: Absolute path to the workspace directory

        Returns:
            URL string with ?folder= parameter

        Example:
            workspace_path = Path("/home/user/mosaic/users/1/1/5")
            url = "http://127.0.0.1:20000/?folder=/home/user/mosaic/users/1/1/5"
        """
        return f"http://{self.host}:{self.port}/?folder={workspace_path}"


    def get_status(self) -> dict:
        """Get current status of the code-server instance

        Returns:
            Status dictionary with:
            - status: Current status string
            - port: Port number (or None if stopped)
            - started_at: Start timestamp (or None if stopped)
            - pid: Process ID (or None if stopped)
        """
        return {
            'status': self.status,
            'port': self.port if self.status == 'running' else None,
            'started_at': self.started_at,
            'pid': self.process.pid if self.process else None
        }


    async def _start_process(self) -> subprocess.Popen:
        """Start code-server subprocess (internal method)

        Business logic:
        1. Build command line arguments (no workspace specified)
        2. Start subprocess with Popen
        3. Return process handle

        Returns:
            subprocess.Popen handle

        Raises:
            OSError: If code-server binary not found or permission denied
            Exception: Other subprocess creation errors

        Notes:
        - Process runs without workspace argument
        - This allows ?folder= parameter to work
        - Binds to configured host and port
        """
        # Build command without workspace
        cmd = [
            self.code_server_binary,
            "--bind-addr", f"{self.host}:{self.port}",
            "--auth", "none",
            "--disable-telemetry",
            "--disable-update-check",
            "--ignore-last-opened",
            "--disable-workspace-trust"
        ]

        logger.info(f"Starting code-server: {' '.join(cmd)}")

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True
            )
            logger.info(f"Code-server process started: pid={process.pid}, port={self.port}")
            return process

        except OSError as e:
            logger.error(f"Failed to start code-server process: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error starting code-server: {e}")
            raise


    async def _wait_for_ready(self, timeout: int = 30) -> bool:
        """Wait for code-server to be ready (health check loop)

        Business logic:
        1. Record start time
        2. Loop until timeout:
           a. Check if process is still alive
           b. Attempt HTTP health check
           c. Sleep 1 second before next attempt
        3. Return success or failure

        Args:
            timeout: Maximum seconds to wait (default: 30)

        Returns:
            True if ready, False if timeout or process died

        Notes:
        - Uses aiohttp for async HTTP requests
        - Each health check has 2 second timeout
        - Checks every 1 second
        """
        start_time = time.time()
        url = f"http://{self.host}:{self.port}/healthz"

        logger.info(f"Waiting for code-server to be ready: port={self.port}")

        while time.time() - start_time < timeout:
            # Check if process is still alive
            if self.process and self.process.poll() is not None:
                logger.error(f"Process died while waiting for ready: pid={self.process.pid}")
                return False

            # Attempt health check
            try:
                check_timeout = aiohttp.ClientTimeout(total=2)
                async with aiohttp.ClientSession(timeout=check_timeout) as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            logger.info(f"Code-server ready: port={self.port}")
                            return True

            except (asyncio.TimeoutError, aiohttp.ClientError):
                # Expected during startup, continue waiting
                pass
            except Exception as e:
                logger.warning(f"Unexpected error during health check: {e}")

            # Wait before next attempt
            await asyncio.sleep(1)

        # Timeout reached
        logger.error(f"Timeout waiting for code-server to be ready: port={self.port}")
        return False


    async def _is_healthy(self) -> bool:
        """Check if instance is healthy (single health check)

        Business logic:
        1. Check if process is alive
        2. Perform HTTP health check
        3. Return result

        Returns:
            True if healthy, False otherwise

        Notes:
        - Quick check with 2 second timeout
        - Does not modify instance state
        """
        # Check if process is still alive
        if not self.process or self.process.poll() is not None:
            logger.warning("Code-server process is not running")
            return False

        # Perform HTTP health check
        url = f"http://{self.host}:{self.port}/healthz"
        try:
            timeout = aiohttp.ClientTimeout(total=2)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        return True
                    logger.warning(f"Health check failed: status={response.status}")
                    return False

        except asyncio.TimeoutError:
            logger.debug("Health check timeout")
            return False
        except aiohttp.ClientError as e:
            logger.debug(f"Health check connection error: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected health check error: {e}")
            return False
