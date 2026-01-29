"""
Mosaic SDK - Python SDK for Mosaic Event Mesh

This package provides a Python SDK for interacting with Mosaic Event Mesh,
enabling programmable calls to nodes within the mesh.

Main Components:
- MosaicSDK: Main entry point for SDK usage
- Authentication: JWT-based authentication management
- Dynamic Proxy: mesh.node.connect() proxy pattern
- API Clients: HTTP client wrappers for backend APIs

Usage:
    from mosaic_sdk import MosaicSDK

    mosaic = MosaicSDK(username="user@example.com", password="password")

    with mosaic.mesh_0.node_1.connect() as node:
        result = node.analyze_data(data=user_data, threshold=0.95)
"""

from .client import MosaicSDK
from .exceptions import (
    MosaicSDKError,
    AuthenticationError,
    ConnectionError,
    SessionError,
    ProgrammableCallError,
)

__version__ = "0.1.0"

__all__ = [
    "MosaicSDK",
    "MosaicSDKError",
    "AuthenticationError",
    "ConnectionError",
    "SessionError",
    "ProgrammableCallError",
]
