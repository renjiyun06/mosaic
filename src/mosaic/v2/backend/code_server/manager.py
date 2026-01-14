"""Code server instance manager.

This module manages the lifecycle of code-server processes, including:
- Port allocation and management
- Process startup and shutdown
- Health checking and monitoring
- Reference counting for shared instances
"""

import asyncio
import logging
import time
import signal
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime
from dataclasses import dataclass
import subprocess

import aiohttp

from ..model import Node

logger = logging.getLogger(__name__)


@dataclass
class CodeServerInstance:
    """Represents a running code-server instance

    Attributes:
        node: Node database model object this instance belongs to
        port: Port number the code-server is listening on
        process: Subprocess handle for the code-server process
        workspace_path: Absolute path to the workspace directory
        started_at: Timestamp when instance was started
        ref_count: Number of active connections/sessions using this instance
        status: Current status ('starting', 'running', 'stopping', 'error')
    """
    node: Node
    port: int
    process: subprocess.Popen
    workspace_path: Path
    started_at: datetime
    ref_count: int
    status: str


class CodeServerManager:
    """Manages code-server process lifecycle

    This manager is responsible for:
    - Creating and destroying code-server instances
    - Port allocation from a configured pool
    - Health checking instances
    - Sharing instances across multiple sessions (per-node basis)
    - Reference counting to determine when to shutdown instances

    Usage:
        manager = CodeServerManager(
            host="127.0.0.1",
            port_range=(20000, 20099),
            code_server_binary="code-server"
        )
        await manager.start()

        # Get or create instance
        instance = await manager.get_or_create_instance(node, workspace_path)

        # Use instance...

        # Release when done (auto-shutdown if ref_count reaches 0)
        await manager.release_instance(node)

        # Cleanup
        await manager.stop()
    """

    def __init__(self,
                 host: str = "127.0.0.1",
                 port_range: tuple[int, int] = (20000, 20099),
                 code_server_binary: str = "code-server"):
        """Initialize CodeServerManager

        Args:
            host: Host address for binding and health checks (default: "127.0.0.1")
            port_range: Tuple of (start_port, end_port) for port allocation pool (default: 20000-20099)
            code_server_binary: Path or name of code-server executable (default: "code-server")

        Notes:
        - host is used for both binding code-server and performing health checks
        - Port pool is initialized with all ports in range as available
        - code_server_binary can be absolute path or command name in PATH
        - Instances are automatically stopped when ref_count reaches 0
        """
        self.host = host
        self.port_range = port_range
        self.code_server_binary = code_server_binary

        # Instance tracking: node.id -> CodeServerInstance
        self.instances: Dict[int, CodeServerInstance] = {}

        # Port to node mapping: port -> node.id
        self.port_to_node: Dict[int, int] = {}

        # Port pool management
        self.available_ports: set = set(range(port_range[0], port_range[1] + 1))
        self.used_ports: set = set()

        # Manager state
        self.running: bool = False
        self.lock: asyncio.Lock = asyncio.Lock()

        logger.info(
            f"CodeServerManager initialized: host={host}, "
            f"port_range={port_range}, binary={code_server_binary}, "
            f"total_ports={len(self.available_ports)}"
        )


    async def start(self):
        """Start the manager (called on application startup)

        Business logic:
        1. Set internal running flag to True
        2. Initialize/reset any state if needed
        3. Log startup completion

        Notes:
        - This should be called in FastAPI lifespan startup
        - Should be idempotent (safe to call multiple times)
        - No background tasks needed (no cleanup loop)
        """
        async with self.lock:
            if self.running:
                logger.warning("CodeServerManager already running")
                return

            self.running = True
            logger.info("CodeServerManager started successfully")


    async def stop(self):
        """Stop the manager and all instances (called on application shutdown)

        Business logic:
        1. Set internal running flag to False
        2. Stop all active instances (force stop, ignore ref_count)
        3. Wait for all instances to terminate
        4. Clear all internal state
        5. Log shutdown completion

        Notes:
        - This should be called in FastAPI lifespan shutdown
        - Forces shutdown of all instances regardless of ref_count
        - Should ensure clean termination of all subprocesses
        """
        async with self.lock:
            if not self.running:
                logger.warning("CodeServerManager not running")
                return

            logger.info("Stopping CodeServerManager...")
            self.running = False

            # Stop all instances (force stop)
            nodes_to_stop = list(self.instances.keys())
            for node_id in nodes_to_stop:
                node = self.instances[node_id].node
                await self.stop_instance(node, force=True)

            # Clear all state
            self.instances.clear()
            self.port_to_node.clear()
            self.used_ports.clear()
            self.available_ports = set(range(self.port_range[0], self.port_range[1] + 1))

            logger.info("CodeServerManager stopped successfully")


    async def get_or_create_instance(self, node: Node, workspace_path: Path) -> CodeServerInstance:
        """Get existing instance or create new one

        Business logic:
        1. Check if instance already exists for this node (using node.id)
        2. If exists:
           a. Perform health check (is_healthy)
           b. If healthy:
              - Increment ref_count
              - Return existing instance
           c. If unhealthy:
              - Log warning about unhealthy instance
              - Stop and cleanup the unhealthy instance
              - Continue to create new instance
        3. If not exists or was unhealthy:
           a. Create new instance (call _create_instance)
           b. Return new instance

        Args:
            node: Node database model object
            workspace_path: Absolute path to node's workspace directory

        Returns:
            Running CodeServerInstance

        Raises:
            RuntimeError: If failed to create instance (no available ports, process failed to start, health check timeout)

        Notes:
        - This method is the main entry point for getting code-server instances
        - Automatically handles instance reuse and recreation
        - Increments ref_count on each call
        - Thread-safe (should use asyncio locks if needed)
        """
        async with self.lock:
            # 1. Check if instance exists
            if node.id in self.instances:
                instance = self.instances[node.id]

                # 2a. Check health
                healthy = await self._is_healthy(instance)

                if healthy:
                    # 2b. Increment ref_count and return
                    instance.ref_count += 1
                    logger.info(
                        f"Reusing existing code-server instance: node_id={node.id}, "
                        f"port={instance.port}, ref_count={instance.ref_count}"
                    )
                    return instance
                else:
                    # 2c. Unhealthy, stop and recreate
                    logger.warning(
                        f"Existing instance unhealthy, recreating: node_id={node.id}, "
                        f"port={instance.port}"
                    )
                    await self.stop_instance(node, force=True)

            # 3. Create new instance
            logger.info(f"Creating new code-server instance: node_id={node.id}")
            instance = await self._create_instance(node, workspace_path)
            return instance


    async def _create_instance(self, node: Node, workspace_path: Path) -> CodeServerInstance:
        """Create and start a new code-server instance (internal method)

        Business logic:
        1. Allocate port from pool:
           a. Call _allocate_port()
           b. If no port available, raise RuntimeError
        2. Start code-server process:
           a. Call _start_process(port, workspace_path)
           b. Catch any subprocess errors and raise RuntimeError
        3. Create CodeServerInstance object:
           a. Initialize with allocated port, process handle, started_at timestamp
           b. Set status='starting', ref_count=1, node=node
        4. Wait for instance to be ready:
           a. Call _wait_for_ready(instance, timeout=30)
           b. If timeout or failure:
              - Terminate process
              - Release port back to pool
              - Raise RuntimeError
           c. If ready:
              - Update status='running'
        5. Record instance in manager:
           a. Add to instances dict (node.id -> instance)
           b. Add to port_to_node mapping (port -> node.id)
        6. Log success and return instance

        Args:
            node: Node database model object
            workspace_path: Absolute path to workspace directory

        Returns:
            Running CodeServerInstance

        Raises:
            RuntimeError: If any step fails

        Notes:
        - This is an internal method, should not be called directly
        - All cleanup on failure should be handled here
        - Startup timeout is 30 seconds
        """
        # 1. Allocate port
        port = self._allocate_port()
        if port is None:
            raise RuntimeError("No available ports in pool")

        process = None
        try:
            # 2. Start process
            process = await self._start_process(port, workspace_path)

            # 3. Create instance object
            instance = CodeServerInstance(
                node=node,
                port=port,
                process=process,
                workspace_path=workspace_path,
                started_at=datetime.now(),
                ref_count=1,
                status='starting'
            )

            # 4. Wait for ready
            ready = await self._wait_for_ready(instance, timeout=30)
            if not ready:
                # Cleanup on failure
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                self._release_port(port)
                raise RuntimeError(f"Code-server failed to start within timeout for node {node.id}")

            # Update status to running
            instance.status = 'running'

            # 5. Record instance
            self.instances[node.id] = instance
            self.port_to_node[port] = node.id

            logger.info(
                f"Code-server instance created successfully: node_id={node.id}, "
                f"port={port}, pid={process.pid}"
            )

            return instance

        except Exception as e:
            # Cleanup on any error
            if process is not None:
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except Exception:
                    try:
                        process.kill()
                        process.wait()
                    except Exception:
                        pass
            self._release_port(port)
            logger.error(f"Failed to create code-server instance for node {node.id}: {e}")
            raise RuntimeError(f"Failed to create code-server instance: {e}")


    async def stop_instance(self, node: Node, force: bool = False):
        """Stop a code-server instance

        Business logic:
        1. Check if instance exists (using node.id):
           a. If not found, log warning and return (idempotent)
        2. Handle reference counting (if not force):
           a. Check if ref_count > 0:
              - Log warning "Stopping instance with active references"
        3. Stop the instance:
           a. Update status='stopping'
           b. Terminate process gracefully (SIGTERM)
           c. Wait for process to exit (timeout: 5 seconds)
           d. If timeout, force kill (SIGKILL)
           e. Wait for process to be fully terminated
        4. Cleanup:
           a. Release port back to pool (_release_port)
           b. Remove from instances dict
           c. Remove from port_to_node mapping
        5. Log completion

        Args:
            node: Node database model object
            force: If True, force stop regardless of ref_count (default: False)

        Notes:
        - Idempotent operation (safe to call multiple times)
        - Uses graceful shutdown with fallback to force kill
        - Force flag is used during manager shutdown
        - With simplified design, this is called when ref_count reaches 0
        """
        # 1. Check if instance exists
        if node.id not in self.instances:
            logger.warning(f"Instance not found for node {node.id}, already stopped")
            return

        instance = self.instances[node.id]

        # 2. Handle reference counting
        if not force and instance.ref_count > 0:
            logger.warning(
                f"Stopping instance with active references: node_id={node.id}, "
                f"ref_count={instance.ref_count}"
            )

        # 3. Stop the instance
        instance.status = 'stopping'
        logger.info(f"Stopping code-server instance: node_id={node.id}, port={instance.port}, pid={instance.process.pid}")

        try:
            # Terminate gracefully
            instance.process.terminate()

            # Wait for process to exit (timeout: 5 seconds)
            try:
                instance.process.wait(timeout=5)
                logger.info(f"Process terminated gracefully: node_id={node.id}, pid={instance.process.pid}")
            except subprocess.TimeoutExpired:
                # Force kill if timeout
                logger.warning(f"Process did not exit gracefully, force killing: node_id={node.id}, pid={instance.process.pid}")
                instance.process.kill()
                instance.process.wait()
                logger.info(f"Process force killed: node_id={node.id}, pid={instance.process.pid}")

        except Exception as e:
            logger.error(f"Error stopping process for node {node.id}: {e}")

        # 4. Cleanup
        self._release_port(instance.port)
        del self.instances[node.id]
        del self.port_to_node[instance.port]

        logger.info(f"Code-server instance stopped: node_id={node.id}")


    async def release_instance(self, node: Node):
        """Release a reference to an instance (decrement ref_count)

        Business logic:
        1. Check if instance exists (using node.id):
           a. If not found, log warning and return (idempotent)
        2. Decrement ref_count:
           a. Ensure ref_count doesn't go below 0
           b. Log the release with new ref_count
        3. Check if should shutdown:
           a. If ref_count == 0:
              - Log "No more references, stopping instance"
              - Call stop_instance(node, force=True)

        Args:
            node: Node database model object

        Notes:
        - This is called when a session/connection closes
        - When ref_count reaches 0, instance is immediately stopped
        - Idempotent operation (safe to call multiple times)
        """
        async with self.lock:
            # 1. Check if instance exists
            if node.id not in self.instances:
                logger.warning(f"Instance not found for node {node.id}, cannot release")
                return

            instance = self.instances[node.id]

            # 2. Decrement ref_count
            if instance.ref_count > 0:
                instance.ref_count -= 1

            logger.info(
                f"Released instance reference: node_id={node.id}, "
                f"new_ref_count={instance.ref_count}"
            )

            # 3. Check if should shutdown
            if instance.ref_count == 0:
                logger.info(f"No more references, stopping instance: node_id={node.id}")
                await self.stop_instance(node, force=True)


    def get_instance_status(self, node: Node) -> Optional[dict]:
        """Get instance status information (synchronous)

        Business logic:
        1. Check if instance exists (using node.id):
           a. If not found, return None
        2. Build status dictionary:
           a. status: Current status string
           b. port: Port number
           c. started_at: Start timestamp
           d. ref_count: Current reference count
        3. Return status dict

        Args:
            node: Node database model object

        Returns:
            Status dictionary or None if instance not found
            Dict format: {
                'status': str,
                'port': int,
                'started_at': datetime,
                'ref_count': int
            }

        Notes:
        - This is a read-only operation
        - Does not perform health check (use _is_healthy for that)
        - Returns current state snapshot
        - URL is constructed by the API layer using configured host
        """
        # 1. Check if instance exists
        if node.id not in self.instances:
            return None

        # 2. Build status dictionary
        instance = self.instances[node.id]
        return {
            'status': instance.status,
            'port': instance.port,
            'started_at': instance.started_at,
            'ref_count': instance.ref_count
        }


    def _allocate_port(self) -> Optional[int]:
        """Allocate an available port from the pool (internal method)

        Business logic:
        1. Check if any ports are available:
           a. If available_ports is empty, return None
        2. Pop a port from available_ports set
        3. Add port to used_ports set
        4. Return the allocated port

        Returns:
            Allocated port number or None if pool exhausted

        Notes:
        - This is a synchronous operation
        - Should be thread-safe if needed (use locks)
        - Port is removed from available pool until released
        """
        if not self.available_ports:
            logger.error("Port pool exhausted, no available ports")
            return None

        port = self.available_ports.pop()
        self.used_ports.add(port)
        logger.debug(f"Allocated port {port}, remaining: {len(self.available_ports)}")
        return port


    def _release_port(self, port: int):
        """Release a port back to the pool (internal method)

        Business logic:
        1. Check if port is in used_ports:
           a. If not, log warning (shouldn't happen)
        2. Remove port from used_ports
        3. Add port back to available_ports

        Args:
            port: Port number to release

        Notes:
        - This is a synchronous operation
        - Port becomes immediately available for reallocation
        """
        if port not in self.used_ports:
            logger.warning(f"Attempting to release port {port} that is not in use")
            return

        self.used_ports.remove(port)
        self.available_ports.add(port)
        logger.debug(f"Released port {port}, available: {len(self.available_ports)}")


    async def _start_process(self, port: int, workspace_path: Path) -> subprocess.Popen:
        """Start code-server subprocess (internal method)

        Business logic:
        1. Build command line arguments:
           a. code-server binary path
           b. workspace_path (positional argument)
           c. --bind-addr {self.host}:{port}
           d. --auth none (no authentication, assume behind auth proxy)
           e. --disable-telemetry
           f. --disable-update-check
        2. Log the command being executed
        3. Start subprocess:
           a. Use subprocess.Popen
           b. Redirect stdout/stderr to PIPE
           c. Use start_new_session=True (detach from parent)
        4. Return process handle

        Args:
            port: Port number to bind code-server to
            workspace_path: Workspace directory to open

        Returns:
            subprocess.Popen handle

        Raises:
            OSError: If code-server binary not found or permission denied
            Exception: Other subprocess creation errors

        Notes:
        - Process is detached from parent (start_new_session=True)
        - Authentication is disabled (assumes running behind auth proxy)
        - Binds to configured host address (from __init__)
        """
        # Build command
        cmd = [
            self.code_server_binary,
            str(workspace_path),
            "--bind-addr", f"{self.host}:{port}",
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
            logger.info(f"Code-server process started: pid={process.pid}, port={port}")
            return process

        except OSError as e:
            logger.error(f"Failed to start code-server process: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error starting code-server: {e}")
            raise


    async def _wait_for_ready(self, instance: CodeServerInstance, timeout: int = 30) -> bool:
        """Wait for code-server to be ready (health check loop)

        Business logic:
        1. Record start time
        2. Loop until timeout:
           a. Check if process is still alive (poll):
              - If dead, log error and return False
           b. Attempt HTTP health check:
              - GET http://{self.host}:{port}/healthz
              - Timeout: 2 seconds per request
              - If status 200, log success and return True
              - If error, continue loop
           c. Sleep 1 second before next attempt
        3. If loop completes without success:
           a. Log timeout error
           b. Return False

        Args:
            instance: CodeServerInstance to check
            timeout: Maximum seconds to wait (default: 30)

        Returns:
            True if ready, False if timeout or process died

        Notes:
        - Uses aiohttp for async HTTP requests
        - Each health check has 2 second timeout
        - Checks every 1 second
        - Process liveness checked on each iteration
        - Uses configured host address for health check requests
        """
        start_time = time.time()
        url = f"http://{self.host}:{instance.port}/healthz"

        logger.info(f"Waiting for code-server to be ready: node_id={instance.node.id}, port={instance.port}")

        while time.time() - start_time < timeout:
            # Check if process is still alive
            if instance.process.poll() is not None:
                logger.error(f"Process died while waiting for ready: node_id={instance.node.id}, pid={instance.process.pid}")
                return False

            # Attempt health check
            try:
                check_timeout = aiohttp.ClientTimeout(total=2)
                async with aiohttp.ClientSession(timeout=check_timeout) as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            logger.info(f"Code-server ready: node_id={instance.node.id}, port={instance.port}")
                            return True

            except (asyncio.TimeoutError, aiohttp.ClientError):
                # Expected during startup, continue waiting
                pass
            except Exception as e:
                logger.warning(f"Unexpected error during health check: {e}")

            # Wait before next attempt
            await asyncio.sleep(1)

        # Timeout reached
        logger.error(f"Timeout waiting for code-server to be ready: node_id={instance.node.id}, port={instance.port}")
        return False


    async def _is_healthy(self, instance: CodeServerInstance) -> bool:
        """Check if instance is healthy (single health check)

        Business logic:
        1. Check if process is alive:
           a. Call process.poll()
           b. If not None (process terminated), return False
        2. Perform HTTP health check:
           a. GET http://{self.host}:{port}/healthz
           b. Timeout: 2 seconds
           c. If status 200, return True
           d. If error (connection refused, timeout, etc.), return False
        3. Return result

        Args:
            instance: CodeServerInstance to check

        Returns:
            True if healthy, False otherwise

        Notes:
        - Quick check with 2 second timeout
        - Used by get_or_create_instance to verify existing instances
        - Does not modify instance state
        - Uses configured host address for health check request
        """
        # Check if process is still alive
        if instance.process.poll() is not None:
            logger.warning(f"Process died for node {instance.node.id}, pid={instance.process.pid}")
            return False

        # Perform HTTP health check
        url = f"http://{self.host}:{instance.port}/healthz"
        try:
            timeout = aiohttp.ClientTimeout(total=2)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        return True
                    logger.warning(f"Health check failed for node {instance.node.id}: status={response.status}")
                    return False

        except asyncio.TimeoutError:
            logger.debug(f"Health check timeout for node {instance.node.id}")
            return False
        except aiohttp.ClientError as e:
            logger.debug(f"Health check connection error for node {instance.node.id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected health check error for node {instance.node.id}: {e}")
            return False
