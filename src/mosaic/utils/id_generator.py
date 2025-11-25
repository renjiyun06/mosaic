"""
Mosaic Utilities - ID Generator

This module provides functions for generating unique identifiers used
throughout the Mosaic system.

ID Format:
- All IDs are URL-safe strings
- Format: {prefix}-{random_hex}
- Prefix indicates the ID type
- Random component uses secrets for cryptographic randomness

Examples:
- Event ID: evt-a1b2c3d4e5f6
- Session ID: sess-1234abcd5678
- Mesh ID: mesh-deadbeef1234
- Node ID: node-cafebabe9012
"""

import secrets
from typing import Optional


def _generate_id(prefix: str, length: int = 12) -> str:
    """
    Generate a unique ID with the given prefix.
    
    Args:
        prefix: Prefix to prepend (e.g., "evt", "sess")
        length: Number of random hex characters (default 12)
    
    Returns:
        ID string in format "{prefix}-{random_hex}"
    """
    random_part = secrets.token_hex(length // 2)
    return f"{prefix}-{random_part}"


def generate_event_id() -> str:
    """
    Generate a unique event ID.
    
    Returns:
        Event ID (e.g., "evt-a1b2c3d4e5f6")
    """
    return _generate_id("evt")


def generate_session_id() -> str:
    """
    Generate a unique session ID.
    
    Returns:
        Session ID (e.g., "sess-1234abcd5678")
    """
    return _generate_id("sess")


def generate_mesh_id(name: Optional[str] = None) -> str:
    """
    Generate a unique mesh ID.
    
    Args:
        name: Optional human-readable name to include
    
    Returns:
        Mesh ID (e.g., "mesh-deadbeef1234" or "mesh-dev-deadbeef")
    
    Example:
        generate_mesh_id()        -> "mesh-a1b2c3d4e5f6"
        generate_mesh_id("dev")   -> "mesh-dev-a1b2c3d4"
    """
    if name:
        random_part = secrets.token_hex(4)
        return f"mesh-{name}-{random_part}"
    return _generate_id("mesh")


def generate_node_id(name: Optional[str] = None) -> str:
    """
    Generate a unique node ID.
    
    Args:
        name: Optional human-readable name to include
    
    Returns:
        Node ID (e.g., "node-cafebabe9012" or "node-worker-cafe")
    
    Example:
        generate_node_id()          -> "node-a1b2c3d4e5f6"
        generate_node_id("worker")  -> "node-worker-a1b2c3d4"
    """
    if name:
        random_part = secrets.token_hex(4)
        return f"node-{name}-{random_part}"
    return _generate_id("node")

