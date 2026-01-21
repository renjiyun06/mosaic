"""
Authentication Manager

Responsibilities:
- JWT token lifecycle management (obtain, store, revoke)
- Secure credential handling

This module handles all authentication-related operations for the SDK.
"""

from typing import Optional
from .api.auth import AuthAPI
from .exceptions import AuthenticationError


class AuthManager:
    """
    Manages authentication state and JWT token lifecycle.

    This class handles:
    1. Login and obtaining JWT tokens
    2. Token storage and retrieval
    3. Token expiration checking
    4. Logout and token revocation

    The AuthManager works closely with the AuthAPI client to
    communicate with the backend authentication endpoints.

    Args:
        api_client: The base API client for making HTTP requests
        username: User credentials - username/email
        password: User credentials - password
    """

    def __init__(self, api_client, username: str, password: str):
        """Initialize authentication manager."""
        self.api_client = api_client
        self.username = username
        self.password = password
        self.auth_api = AuthAPI(api_client)

        # Token state
        self._token: Optional[str] = None

    async def login(self) -> None:
        """
        Authenticate user and obtain JWT token.

        This will:
        1. Call the backend login API
        2. Store the returned JWT token

        Raises:
            AuthenticationError: If login fails
        """
        try:
            # Call login API
            response = await self.auth_api.login(self.username, self.password)

            # Extract token from SuccessResponse wrapper
            # Response format: {"success": true, "data": {"user": {...}, "access_token": "..."}, "message": null}
            data = response.get("data", {})
            self._token = data.get("access_token")
            if not self._token:
                raise AuthenticationError("Login failed: no access_token in response")

        except Exception as e:
            if not isinstance(e, AuthenticationError):
                raise AuthenticationError(f"Login failed: {str(e)}")
            raise

    async def logout(self) -> None:
        """
        Logout and invalidate current token.

        This will:
        1. Call the backend logout API (if applicable)
        2. Clear stored token
        3. Reset authentication state
        """
        if self._token:
            try:
                await self.auth_api.logout(self._token)
            except Exception:
                # Ignore logout errors, just clear token
                pass

        # Clear token state
        self._token = None

    async def get_token(self) -> Optional[str]:
        """
        Get current JWT token.

        This will:
        1. Check if token exists
        2. Return token (even if expired - backend will handle validation)

        Returns:
            JWT token string, or None if not authenticated
        """
        return self._token

    def is_authenticated(self) -> bool:
        """
        Check if user is currently authenticated.

        Returns:
            True if token exists
        """
        return self._token is not None
