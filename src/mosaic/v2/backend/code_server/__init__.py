"""Code server management module for workspace mode.

This module provides code-server process lifecycle management for interactive
VS Code workspace sessions. It handles instance creation, port allocation,
health checking, and automatic cleanup.

Components:
- CodeServerManager: Global manager for all code-server instances
"""

from .manager import CodeServerManager

__all__ = ['CodeServerManager']
