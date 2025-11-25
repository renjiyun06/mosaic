"""
Unix Domain Socket Signal Mechanism

This module provides lightweight inter-process signaling using
Unix Domain Sockets (UDS). It enables efficient event notification
without polling the database.

Architecture:
-------------
1. Each node has a UDS socket at ~/.mosaic/<mesh_id>/sockets/<node_id>.sock
2. When an event is sent, the sender notifies the target via UDS
3. The target wakes up from blocking and checks the database

Why UDS:
--------
- Much lower latency than polling
- No external dependencies (unlike Redis pub/sub)
- Works well with SQLite's file-based nature
- Efficient for local inter-process communication

Signal Protocol:
----------------
- Signal is a single byte: b'1'
- No acknowledgment required (fire-and-forget)
- Multiple signals can coalesce (node just wakes up and checks DB)

Components:
-----------
- SignalListener: Server-side, waits for wake-up signals
- SignalClient: Client-side, sends wake-up signals to nodes
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional

from mosaic.core.types import NodeId


logger = logging.getLogger(__name__)


# Signal byte to send (arbitrary, just needs to be non-empty)
SIGNAL_BYTE = b"1"

# Timeout for signal operations
SIGNAL_TIMEOUT_SECONDS = 5.0


class SignalListener:
    """
    Listens for wake-up signals via Unix Domain Socket.
    
    Each node creates a SignalListener that:
    1. Creates a UDS socket at the configured path
    2. Accepts connections and reads signal bytes
    3. Signals an internal asyncio.Event when woken up
    
    Usage:
        listener = SignalListener(socket_path)
        await listener.start()
        
        try:
            # Wait for signal or timeout
            signaled = await listener.wait_for_signal(timeout=30.0)
            if signaled:
                # Check database for new events
                ...
        finally:
            await listener.stop()
    
    Thread Safety:
        SignalListener is not thread-safe. Use one instance per
        asyncio event loop.
    """
    
    def __init__(self, socket_path: Path) -> None:
        """
        Initialize the signal listener.
        
        Args:
            socket_path: Path for the UDS socket file
        """
        self._socket_path = socket_path
        self._server: Optional[asyncio.AbstractServer] = None
        self._wake_event = asyncio.Event()
        self._running = False
    
    @property
    def socket_path(self) -> Path:
        """Path to the UDS socket."""
        return self._socket_path
    
    @property
    def is_running(self) -> bool:
        """Check if the listener is running."""
        return self._running
    
    async def start(self) -> None:
        """
        Start the signal listener.
        
        Creates the UDS socket and begins accepting connections.
        
        Raises:
            OSError: If socket cannot be created
        """
        if self._running:
            return
        
        # Ensure parent directory exists
        self._socket_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Remove stale socket file if exists
        if self._socket_path.exists():
            self._socket_path.unlink()
        
        # Create Unix domain socket server
        self._server = await asyncio.start_unix_server(
            self._handle_connection,
            path=str(self._socket_path),
        )
        
        self._running = True
        logger.debug(f"Signal listener started at {self._socket_path}")
    
    async def stop(self) -> None:
        """
        Stop the signal listener.
        
        Closes the server and removes the socket file.
        """
        if not self._running:
            return
        
        self._running = False
        
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        
        # Remove socket file
        if self._socket_path.exists():
            try:
                self._socket_path.unlink()
            except OSError:
                pass  # Ignore errors during cleanup
        
        logger.debug(f"Signal listener stopped at {self._socket_path}")
    
    async def _handle_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """
        Handle an incoming signal connection.
        
        Reads signal bytes and triggers the wake event.
        """
        try:
            # Read signal byte (we don't care about the content)
            data = await asyncio.wait_for(
                reader.read(1),
                timeout=SIGNAL_TIMEOUT_SECONDS,
            )
            
            if data:
                # Signal received - wake up waiters
                self._wake_event.set()
                logger.debug(f"Signal received at {self._socket_path}")
        
        except asyncio.TimeoutError:
            logger.warning(f"Signal connection timed out at {self._socket_path}")
        
        except Exception as e:
            logger.warning(f"Error handling signal at {self._socket_path}: {e}")
        
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
    
    async def wait_for_signal(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for a wake-up signal.
        
        Blocks until a signal is received or timeout expires.
        
        Args:
            timeout: Maximum seconds to wait (None for indefinite)
        
        Returns:
            True if signal was received, False if timeout expired
        """
        # Clear the event before waiting
        self._wake_event.clear()
        
        try:
            if timeout is not None:
                await asyncio.wait_for(
                    self._wake_event.wait(),
                    timeout=timeout,
                )
            else:
                await self._wake_event.wait()
            
            return True
        
        except asyncio.TimeoutError:
            return False
    
    def clear(self) -> None:
        """Clear any pending signals."""
        self._wake_event.clear()


class SignalClient:
    """
    Sends wake-up signals to nodes via Unix Domain Socket.
    
    When an event is sent to a target node, the sender uses
    SignalClient to notify the target that an event is waiting.
    
    Usage:
        client = SignalClient(sockets_dir)
        
        # Notify a node
        await client.notify("target-node")
    
    Connection Handling:
        - Connections are fire-and-forget
        - Failures are logged but not raised (best effort)
        - Multiple notifications can coalesce
    """
    
    def __init__(self, sockets_dir: Path) -> None:
        """
        Initialize the signal client.
        
        Args:
            sockets_dir: Directory containing node socket files
        """
        self._sockets_dir = sockets_dir
    
    def _get_socket_path(self, node_id: NodeId) -> Path:
        """Get the socket path for a node."""
        return self._sockets_dir / f"{node_id}.sock"
    
    async def notify(self, node_id: NodeId) -> bool:
        """
        Send a wake-up signal to a node.
        
        This is a best-effort operation. If the node's socket
        doesn't exist or is unavailable, the notification fails
        silently (the node will eventually poll the database).
        
        Args:
            node_id: The node to notify
        
        Returns:
            True if signal was sent successfully, False otherwise
        """
        socket_path = self._get_socket_path(node_id)
        
        if not socket_path.exists():
            logger.debug(f"Socket not found for node {node_id}, skipping signal")
            return False
        
        try:
            # Connect to the node's socket
            reader, writer = await asyncio.wait_for(
                asyncio.open_unix_connection(str(socket_path)),
                timeout=SIGNAL_TIMEOUT_SECONDS,
            )
            
            # Send signal byte
            writer.write(SIGNAL_BYTE)
            await writer.drain()
            
            # Close connection
            writer.close()
            await writer.wait_closed()
            
            logger.debug(f"Signal sent to node {node_id}")
            return True
        
        except asyncio.TimeoutError:
            logger.warning(f"Timeout sending signal to node {node_id}")
            return False
        
        except ConnectionRefusedError:
            logger.debug(f"Connection refused by node {node_id} (not running?)")
            return False
        
        except FileNotFoundError:
            logger.debug(f"Socket file not found for node {node_id}")
            return False
        
        except Exception as e:
            logger.warning(f"Error sending signal to node {node_id}: {e}")
            return False
    
    async def notify_multiple(self, node_ids: list[NodeId]) -> dict[NodeId, bool]:
        """
        Send wake-up signals to multiple nodes concurrently.
        
        Args:
            node_ids: List of nodes to notify
        
        Returns:
            Dict mapping node_id to success/failure
        """
        if not node_ids:
            return {}
        
        # Send all signals concurrently
        tasks = [self.notify(node_id) for node_id in node_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Build result dict
        return {
            node_id: (result is True)
            for node_id, result in zip(node_ids, results)
        }

