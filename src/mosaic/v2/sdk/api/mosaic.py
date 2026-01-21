"""
Mosaic API Client

Responsibilities:
- List mosaics endpoint wrapper
- Mosaic name to ID resolution
- Mosaic information retrieval

This module wraps backend mosaic management endpoints.
"""

from typing import Dict, List, Optional
from .base import APIClient
from ..exceptions import NotFoundError, ValidationError


class MosaicAPI:
    """
    API client for Mosaic endpoints.

    Endpoints:
    - GET /api/mosaics

    Args:
        api_client: Base APIClient instance
    """

    def __init__(self, api_client: APIClient):
        """Initialize mosaic API client."""
        self.api_client = api_client

    async def list_mosaics(self) -> List[Dict]:
        """
        List all mosaics owned by current user.

        Returns:
            List of mosaic information dicts

        Raises:
            AuthenticationError: If not authenticated
        """
        # Send list mosaics request
        response = await self.api_client.get("/api/mosaics")

        # Extract data from SuccessResponse wrapper
        # Response format: {"success": true, "data": [...], "message": null}
        data = response.get("data", [])
        return data

    async def resolve_name_to_id(self, name: str) -> int:
        """
        Resolve mosaic name to database ID.

        This will query all mosaics and find the one matching the name.
        If multiple mosaics with the same name exist, raises an error.

        Args:
            name: Mosaic name to resolve

        Returns:
            Mosaic database ID

        Raises:
            NotFoundError: If no mosaic with this name exists
            ValidationError: If multiple mosaics with this name exist
        """
        # Get all mosaics for current user
        mosaics = await self.list_mosaics()

        # Filter by name
        matching_mosaics = [m for m in mosaics if m.get("name") == name]

        if len(matching_mosaics) == 0:
            raise NotFoundError(f"No mosaic found with name '{name}'")

        if len(matching_mosaics) > 1:
            mosaic_ids = [m.get("id") for m in matching_mosaics]
            raise ValidationError(
                f"Multiple mosaics found with name '{name}' (IDs: {mosaic_ids}). "
                f"Please use a unique mosaic name or access by ID directly."
            )

        # Return the unique mosaic ID
        return matching_mosaics[0].get("id")
