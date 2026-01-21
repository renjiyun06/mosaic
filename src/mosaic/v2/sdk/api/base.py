"""
Base API Client

Responsibilities:
- HTTP client lifecycle management (using httpx)
- Common HTTP methods (GET, POST, PUT, DELETE)
- Request/response handling and error conversion
- JWT token injection for authenticated requests
- Connection pooling and timeout management

This is the base class for all API clients.
"""

from typing import Any, Dict, Optional
import httpx
from ..exceptions import AuthenticationError, ConnectionError, MosaicSDKError
from ..utils import build_api_url


class APIClient:
    """
    Base HTTP client for making requests to Mosaic backend.

    This class provides:
    1. HTTP methods (get, post, put, delete)
    2. Automatic JWT token injection
    3. Error handling and exception conversion
    4. Connection pooling via httpx

    All specific API clients (AuthAPI, ProgrammableCallAPI) should
    use this base client for HTTP communication.

    Args:
        base_url: Backend API base URL (e.g., "http://localhost:8000")
        timeout: Request timeout in seconds
        auth_manager: Optional AuthManager for token injection
    """

    def __init__(
        self,
        base_url: str,
        timeout: int = 30,
        auth_manager: Optional[Any] = None,
    ):
        """Initialize API client."""
        self.base_url = base_url
        self.timeout = timeout
        self.auth_manager = auth_manager
        self.client = httpx.AsyncClient(timeout=timeout)

    async def get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Send GET request.

        Args:
            path: API endpoint path (e.g., "/api/v2/meshes")
            params: Query parameters
            headers: Additional headers

        Returns:
            Response JSON as dict

        Raises:
            MosaicSDKError: On HTTP errors or network issues
        """
        url = build_api_url(self.base_url, path)
        headers = await self._inject_auth_header(headers)

        try:
            response = await self.client.get(url, params=params, headers=headers)
            return self._handle_response(response)
        except httpx.RequestError as e:
            raise ConnectionError(f"Request failed: {str(e)}")

    async def post(
        self,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Send POST request.

        Args:
            path: API endpoint path
            json: Request body as dict
            headers: Additional headers

        Returns:
            Response JSON as dict

        Raises:
            MosaicSDKError: On HTTP errors or network issues
        """
        url = build_api_url(self.base_url, path)
        headers = await self._inject_auth_header(headers)

        try:
            response = await self.client.post(url, json=json, headers=headers)
            return self._handle_response(response)
        except httpx.RequestError as e:
            raise ConnectionError(f"Request failed: {str(e)}")

    async def put(
        self,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Send PUT request.

        Args:
            path: API endpoint path
            json: Request body as dict
            headers: Additional headers

        Returns:
            Response JSON as dict
        """
        url = build_api_url(self.base_url, path)
        headers = await self._inject_auth_header(headers)

        try:
            response = await self.client.put(url, json=json, headers=headers)
            return self._handle_response(response)
        except httpx.RequestError as e:
            raise ConnectionError(f"Request failed: {str(e)}")

    async def delete(
        self,
        path: str,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Send DELETE request.

        Args:
            path: API endpoint path
            headers: Additional headers

        Returns:
            Response JSON as dict
        """
        url = build_api_url(self.base_url, path)
        headers = await self._inject_auth_header(headers)

        try:
            response = await self.client.delete(url, headers=headers)
            return self._handle_response(response)
        except httpx.RequestError as e:
            raise ConnectionError(f"Request failed: {str(e)}")

    async def _inject_auth_header(self, headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """
        Inject JWT token into request headers.

        Args:
            headers: Existing headers dict

        Returns:
            Headers dict with Authorization header added
        """
        if headers is None:
            headers = {}

        # Inject JWT token if auth manager is available
        if self.auth_manager:
            token = await self.auth_manager.get_token()
            if token:
                headers["Authorization"] = f"Bearer {token}"

        return headers

    def _handle_response(self, response: httpx.Response) -> Dict[str, Any]:
        """
        Handle HTTP response and convert errors.

        Args:
            response: httpx Response object

        Returns:
            Response JSON as dict

        Raises:
            AuthenticationError: On 401
            ConnectionError: On network errors
            MosaicSDKError: On other errors
        """
        # Handle successful responses
        if response.status_code >= 200 and response.status_code < 300:
            # Return empty dict if no content
            if response.status_code == 204 or not response.content:
                return {}
            try:
                return response.json()
            except Exception:
                return {}

        # Handle error responses
        if response.status_code == 401:
            raise AuthenticationError("Authentication failed: invalid or expired token")

        if response.status_code == 404:
            raise ConnectionError(f"Resource not found: {response.url}")

        # Try to extract error message from response
        try:
            error_data = response.json()
            error_message = error_data.get("detail", error_data.get("message", str(error_data)))
        except Exception:
            error_message = response.text or f"HTTP {response.status_code}"

        raise MosaicSDKError(f"Request failed: {error_message}", details={"status_code": response.status_code})

    async def close(self):
        """Close HTTP client and cleanup resources."""
        await self.client.aclose()

    async def __aenter__(self):
        """Async context manager support."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cleanup on exit."""
        await self.close()
