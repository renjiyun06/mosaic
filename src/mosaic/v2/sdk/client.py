"""
MosaicSDK Main Client

Responsibilities:
- SDK initialization and configuration
- Authentication lifecycle management (login/logout)
- Entry point for mesh proxy creation
- Global HTTP client management

This is the main entry point for users of the SDK.
"""

from typing import Optional
from .auth import AuthManager
from .proxy import MosaicProxy
from .api.base import APIClient


class MosaicSDK:
    """
    Main SDK client for Mosaic Event Mesh.

    This class handles:
    1. User authentication (auto-login on initialization)
    2. HTTP client lifecycle
    3. Dynamic mesh proxy creation via __getattr__

    Usage:
        mosaic = MosaicSDK(username="user", password="pass")

        with mosaic.my_mosaic.node_1.connect() as node:
            result = node.task_a(data=x)

    Args:
        username: User email or username
        password: User password
        base_url: Backend API base URL (default: http://localhost:8000)
        timeout: HTTP request timeout in seconds (default: 30)
        auto_login: Automatically login on initialization (default: True)
    """

    def __init__(
        self,
        username: str,
        password: str,
        base_url: str = "http://localhost:8000",
        timeout: int = 30,
        auto_login: bool = False,
    ):
        """
        Initialize Mosaic SDK.

        Note: __init__ cannot be async, so auto_login is disabled by default.
        Use async with statement or manually call await sdk.login().
        """
        self.username = username
        self.password = password
        self.base_url = base_url
        self.timeout = timeout
        self._auto_login = auto_login

        # Create API client
        self.api_client = APIClient(base_url=base_url, timeout=timeout)

        # Create auth manager
        self.auth_manager = AuthManager(
            api_client=self.api_client,
            username=username,
            password=password
        )

        # Set auth manager reference in api_client for token injection
        self.api_client.auth_manager = self.auth_manager

    def get_mosaic(self, mosaic_name: str) -> MosaicProxy:
        """
        Get mosaic proxy by name.

        This method is useful when mosaic name contains special characters
        that are not valid Python identifiers (e.g., "mosaic-1", "mosaic.test").

        Example:
            # For names with special characters
            mosaic = sdk.get_mosaic("mosaic-1")
            mosaic = sdk.get_mosaic("mosaic.test")

            # For regular names, you can use either way
            mosaic = sdk.get_mosaic("my_mosaic")
            mosaic = sdk.my_mosaic  # Same as above

        Args:
            mosaic_name: The mosaic name (can contain any characters)

        Returns:
            MosaicProxy instance for the specified mosaic
        """
        return MosaicProxy(sdk=self, mosaic_name=mosaic_name)

    def __getattr__(self, mosaic_name: str) -> MosaicProxy:
        """
        Dynamically create mosaic proxy on attribute access.

        Example:
            mosaic.my_mosaic  # Returns MosaicProxy for mosaic named "my_mosaic"
            mosaic.test_mosaic  # Returns MosaicProxy for mosaic named "test_mosaic"

        Note:
            For mosaic names with special characters (e.g., "mosaic-1"),
            use get_mosaic() method instead: sdk.get_mosaic("mosaic-1")

        Args:
            mosaic_name: The mosaic name (e.g., "my_mosaic", "test_mosaic")

        Returns:
            MosaicProxy instance for the specified mosaic
        """
        return MosaicProxy(sdk=self, mosaic_name=mosaic_name)

    async def login(self) -> None:
        """
        Manually trigger login.

        Usage:
            await sdk.login()
        """
        await self.auth_manager.login()

    async def logout(self) -> None:
        """
        Logout and invalidate current session.

        This will clear the stored JWT token.
        """
        await self.auth_manager.logout()

    def is_authenticated(self) -> bool:
        """
        Check if user is currently authenticated.

        Returns:
            True if valid JWT token exists, False otherwise
        """
        return self.auth_manager.is_authenticated()

    async def __aenter__(self):
        """
        Async context manager support for SDK lifecycle.

        Usage:
            async with MosaicSDK(username="user", password="pass") as mosaic:
                # Use mosaic
                pass
            # Auto logout on exit
        """
        # Auto login if enabled
        if self._auto_login:
            await self.login()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cleanup on context manager exit."""
        await self.logout()
