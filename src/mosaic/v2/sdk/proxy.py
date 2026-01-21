"""
Dynamic Proxy Layer

Responsibilities:
- Implement mosaic.node.method() dynamic proxy pattern
- Provide connect() context manager for session management
- Handle method call routing to Programmable Call API
- Manage sessionized node instances
- Resolve mosaic name to database ID

This module implements the core dynamic proxy mechanism that enables
the clean SDK API: mosaic.mosaic_name.node_1.connect()
"""

from typing import Any, Dict, Optional
from .api.programmable import ProgrammableCallAPI
from .api.mosaic import MosaicAPI


class MosaicProxy:
    """
    Proxy object for a mosaic.

    Provides dynamic node access via __getattr__.

    This proxy handles lazy resolution of mosaic name to database ID.
    The first time the mosaic is used, it queries the backend to resolve
    the name to the database ID.

    Usage:
        mosaic = MosaicProxy(sdk, "mosaic_name")
        node = mosaic.node_1  # Returns NodeProxy

    Args:
        sdk: Parent MosaicSDK instance
        mosaic_name: Mosaic name identifier
    """

    def __init__(self, sdk, mosaic_name: str):
        """Initialize mosaic proxy."""
        self.sdk = sdk
        self.mosaic_name = mosaic_name
        self._mosaic_id: Optional[int] = None  # Cached database ID

    async def _resolve_mosaic_id(self) -> int:
        """
        Resolve mosaic name to database ID.

        This queries the backend API to find the mosaic ID for the given name.
        The result is cached for subsequent calls.

        Returns:
            Mosaic database ID

        Raises:
            NotFoundError: If no mosaic with this name exists
            ValidationError: If multiple mosaics with this name exist
        """
        if self._mosaic_id is not None:
            return self._mosaic_id

        # Query backend to resolve name to ID
        mosaic_api = MosaicAPI(self.sdk.api_client)
        self._mosaic_id = await mosaic_api.resolve_name_to_id(self.mosaic_name)
        return self._mosaic_id

    def get_node(self, node_id: str) -> 'NodeProxy':
        """
        Get node proxy by ID.

        This method is useful when node ID contains special characters
        that are not valid Python identifiers (e.g., "node-1", "node.test").

        Example:
            # For node IDs with special characters
            node = mosaic.get_node("node-1")
            node = mosaic.get_node("node.test")

            # For regular IDs, you can use either way
            node = mosaic.get_node("analyst")
            node = mosaic.analyst  # Same as above

        Args:
            node_id: The node identifier (can contain any characters)

        Returns:
            NodeProxy instance for the specified node
        """
        return NodeProxy(mosaic_proxy=self, node_id=node_id)

    def __getattr__(self, node_id: str) -> 'NodeProxy':
        """
        Dynamically create node proxy on attribute access.

        Example:
            mosaic.node_1  # Returns NodeProxy for node_1
            mosaic.analyst  # Returns NodeProxy for analyst

        Note:
            For node IDs with special characters (e.g., "node-1"),
            use get_node() method instead: mosaic.get_node("node-1")

        Args:
            node_id: The node identifier

        Returns:
            NodeProxy instance for the specified node
        """
        return NodeProxy(mosaic_proxy=self, node_id=node_id)


class NodeProxy:
    """
    Proxy object for a node.

    Provides connect() method to establish session and
    return sessionized node instance.

    Usage:
        node = NodeProxy(mosaic_proxy, "node_1")
        with node.connect() as sessionized_node:
            result = sessionized_node.task_a(data=x)

    Args:
        mosaic_proxy: Parent MosaicProxy instance
        node_id: Node identifier
    """

    def __init__(self, mosaic_proxy: MosaicProxy, node_id: str):
        """Initialize node proxy."""
        self.mosaic_proxy = mosaic_proxy
        self.node_id = node_id

    def connect(self, session_id: Optional[str] = None) -> 'NodeConnection':
        """
        Create a connection context manager for this node.

        This returns a context manager that:
        1. Creates a new session (or uses specified session_id)
        2. Returns a SessionizedNode instance
        3. Automatically destroys the session on exit

        Args:
            session_id: Optional session ID to reuse existing session

        Returns:
            NodeConnection context manager

        Usage:
            async with node.connect() as session_node:
                result = await session_node.task_a()
        """
        return NodeConnection(node_proxy=self, session_id=session_id)


class NodeConnection:
    """
    Context manager for node connection (session lifecycle).

    Responsibilities:
    1. Create session on __enter__
    2. Return SessionizedNode instance
    3. Destroy session on __exit__

    Args:
        node_proxy: Parent NodeProxy instance
        session_id: Optional session ID to reuse
    """

    def __init__(self, node_proxy: NodeProxy, session_id: Optional[str] = None):
        """Initialize connection context manager."""
        self.node_proxy = node_proxy
        self.custom_session_id = session_id
        self.session_id: Optional[str] = None
        self.programmable_api: Optional[ProgrammableCallAPI] = None

    async def __aenter__(self) -> 'SessionizedNode':
        """
        Enter context: create session and return sessionized node.

        This will:
        1. Create a new session via backend API (or use custom session_id)
        2. Store the session_id
        3. Return SessionizedNode instance

        Returns:
            SessionizedNode instance for making method calls
        """
        # Get API client from SDK
        sdk = self.node_proxy.mosaic_proxy.sdk
        api_client = sdk.api_client
        self.programmable_api = ProgrammableCallAPI(api_client)

        # Create session or use custom session_id
        if self.custom_session_id:
            self.session_id = self.custom_session_id
        else:
            self.session_id = await self._create_session()

        # Return sessionized node
        return SessionizedNode(node_proxy=self.node_proxy, session_id=self.session_id)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Exit context: destroy session.

        This will call backend API to destroy the session
        (unless using custom session_id).
        """
        # Only destroy session if it was created by us (not custom)
        if not self.custom_session_id and self.session_id:
            try:
                await self._destroy_session()
            except Exception:
                # Ignore errors during cleanup
                pass

    async def _create_session(self) -> str:
        """
        Create a new session via backend API.

        Returns:
            Created session ID
        """
        # Resolve mosaic name to database ID
        mosaic_id = await self.node_proxy.mosaic_proxy._resolve_mosaic_id()
        node_id = self.node_proxy.node_id

        return await self.programmable_api.create_session(mosaic_id, node_id)

    async def _destroy_session(self) -> None:
        """Close the session via backend API."""
        if self.session_id:
            # Resolve mosaic name to database ID
            mosaic_id = await self.node_proxy.mosaic_proxy._resolve_mosaic_id()
            await self.programmable_api.close_session(mosaic_id, self.session_id)


class SessionizedNode:
    """
    Sessionized node instance with active session.

    This object is returned from NodeConnection context manager
    and provides dynamic method calling via __getattr__.

    All method calls are routed to the Programmable Call API
    with the associated session_id.

    Usage:
        # Inside with block:
        result = sessionized_node.analyze_data(data=x, threshold=0.95)

    Args:
        node_proxy: Parent NodeProxy instance
        session_id: Active session ID
    """

    def __init__(self, node_proxy: NodeProxy, session_id: str):
        """Initialize sessionized node."""
        self.node_proxy = node_proxy
        self.session_id = session_id

        # Get API client from SDK
        sdk = node_proxy.mosaic_proxy.sdk
        self.programmable_api = ProgrammableCallAPI(sdk.api_client)

    def __getattr__(self, method_name: str):
        """
        Dynamically create callable for any method name.

        This returns a callable that will invoke the Programmable Call API.

        Args:
            method_name: The method to call on the remote node

        Returns:
            Callable that accepts (**kwargs) and returns result

        Example:
            sessionized_node.analyze_data  # Returns callable
            await sessionized_node.analyze_data(data=x)  # Invokes API call
        """
        return self._create_method_callable(method_name)

    def _create_method_callable(self, method_name: str):
        """
        Create a callable function for the given method name.

        The returned function will:
        1. Accept **kwargs as method parameters
        2. Call Programmable Call API with session_id and method
        3. Wait for result and return it

        Args:
            method_name: Method to call

        Returns:
            Async callable function
        """
        async def method_call(**kwargs):
            """
            Execute programmable call for this method.

            Args:
                **kwargs: Method parameters

            Returns:
                Method execution result
            """
            # Resolve mosaic name to database ID
            mosaic_id = await self.node_proxy.mosaic_proxy._resolve_mosaic_id()
            node_id = self.node_proxy.node_id

            # Build instruction from method name and kwargs
            instruction = f"Call method '{method_name}' with the provided parameters"

            # Execute programmable call
            result = await self.programmable_api.execute(
                mosaic_id=mosaic_id,
                node_id=node_id,
                session_id=self.session_id,
                method=method_name,
                instruction=instruction,
                kwargs=kwargs
            )

            return result

        return method_call
