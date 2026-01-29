"""
API Client Package

This package contains HTTP client implementations for
communicating with Mosaic backend APIs.

Modules:
- base: Base HTTP client with common functionality
- auth: Authentication API endpoints
- programmable: Programmable Call API endpoints
"""

from .base import APIClient
from .auth import AuthAPI
from .programmable import ProgrammableCallAPI

__all__ = [
    "APIClient",
    "AuthAPI",
    "ProgrammableCallAPI",
]
