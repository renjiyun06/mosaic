"""
Authentication API Client

Responsibilities:
- Login endpoint wrapper
- Logout endpoint wrapper
- User authentication related API calls

This module wraps backend authentication endpoints.
"""

from typing import Dict
from .base import APIClient


class AuthAPI:
    """
    API client for authentication endpoints.

    Endpoints:
    - POST /api/auth/login
    - POST /api/auth/logout

    Args:
        api_client: Base APIClient instance
    """

    def __init__(self, api_client: APIClient):
        """Initialize authentication API client."""
        self.api_client = api_client

    async def login(self, username: str, password: str) -> Dict[str, str]:
        """
        Authenticate user and obtain JWT token.

        Args:
            username: User email or username
            password: User password

        Returns:
            Dict containing:
            - access_token: JWT token
            - token_type: "Bearer"
            - expires_in: Token expiration seconds

        Raises:
            AuthenticationError: If credentials are invalid
        """
        # Send login request
        # Backend expects 'username_or_email' field (not 'username')
        response = await self.api_client.post(
            "/api/auth/login",
            json={"username_or_email": username, "password": password}
        )
        return response

    async def logout(self, token: str) -> None:
        """
        Logout and invalidate token.

        Args:
            token: JWT token to invalidate
        """
        # Send logout request
        await self.api_client.post(
            "/api/auth/logout",
            json={"token": token}
        )
