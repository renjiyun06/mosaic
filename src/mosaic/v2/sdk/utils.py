"""
Utility Functions

Responsibilities:
- Common helper functions
- JWT token parsing and validation
- Schema validation helpers
- Data transformation utilities

This module contains utility functions used across the SDK.
"""

from typing import Any, Dict
from datetime import datetime, timezone
import json
import base64
from .exceptions import ValidationError


def parse_jwt_token(token: str) -> Dict[str, Any]:
    """
    Parse JWT token and extract payload.

    This decodes the JWT token without verification (verification
    happens on the backend).

    Args:
        token: JWT token string

    Returns:
        Decoded token payload as dict

    Raises:
        ValidationError: If token format is invalid
    """
    try:
        # JWT format: header.payload.signature
        parts = token.split('.')
        if len(parts) != 3:
            raise ValidationError("Invalid JWT token format: expected 3 parts separated by '.'")

        # Decode payload (second part)
        payload_part = parts[1]

        # Add padding if needed (JWT base64 may not have padding)
        padding = 4 - len(payload_part) % 4
        if padding != 4:
            payload_part += '=' * padding

        # Decode base64
        payload_bytes = base64.urlsafe_b64decode(payload_part)
        payload = json.loads(payload_bytes.decode('utf-8'))

        return payload
    except (ValueError, json.JSONDecodeError) as e:
        raise ValidationError(f"Failed to parse JWT token: {str(e)}")


def get_token_expiration(token: str) -> datetime:
    """
    Extract expiration time from JWT token.

    Args:
        token: JWT token string

    Returns:
        Token expiration datetime

    Raises:
        ValidationError: If token is invalid or missing exp claim
    """
    payload = parse_jwt_token(token)

    if 'exp' not in payload:
        raise ValidationError("JWT token missing 'exp' claim")

    # JWT exp is Unix timestamp (seconds since epoch)
    exp_timestamp = payload['exp']
    return datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)


def is_token_expired(token: str, buffer_seconds: int = 300) -> bool:
    """
    Check if JWT token is expired.

    Args:
        token: JWT token string
        buffer_seconds: Consider token expired N seconds before actual expiration
                       (default: 5 minutes)

    Returns:
        True if token is expired or about to expire
    """
    try:
        exp_time = get_token_expiration(token)
        now = datetime.now(timezone.utc)

        # Check if token is expired or about to expire within buffer time
        from datetime import timedelta
        return now >= (exp_time - timedelta(seconds=buffer_seconds))
    except ValidationError:
        # If we can't parse the token, consider it expired
        return True


def validate_json_schema(instance: Any, schema: Dict[str, Any]) -> None:
    """
    Validate data against JSON schema.

    This is a wrapper around jsonschema.validate with better error messages.

    Args:
        instance: Data to validate
        schema: JSON schema dict

    Raises:
        ValidationError: If validation fails
    """
    try:
        import jsonschema
        jsonschema.validate(instance=instance, schema=schema)
    except ImportError:
        raise ValidationError(
            "jsonschema library is required for schema validation. "
            "Install it with: pip install jsonschema"
        )
    except jsonschema.ValidationError as e:
        raise ValidationError(f"Schema validation failed: {e.message}")


def sanitize_error_message(message: str) -> str:
    """
    Sanitize error message to remove sensitive information.

    Args:
        message: Raw error message

    Returns:
        Sanitized error message
    """
    import re

    # Remove potential passwords
    message = re.sub(r'password["\']?\s*[:=]\s*["\']?[^"\'&\s]+', 'password=***', message, flags=re.IGNORECASE)

    # Remove potential tokens
    message = re.sub(r'(token|jwt|bearer)["\']?\s*[:=]\s*["\']?[\w\-\.]+', r'\1=***', message, flags=re.IGNORECASE)

    # Remove potential API keys
    message = re.sub(r'(api[_-]?key)["\']?\s*[:=]\s*["\']?[\w\-]+', r'\1=***', message, flags=re.IGNORECASE)

    return message


def build_api_url(base_url: str, path: str) -> str:
    """
    Build full API URL from base URL and path.

    Handles proper joining of URL components.

    Args:
        base_url: Base URL (e.g., "http://localhost:8000")
        path: API path (e.g., "/api/v2/meshes")

    Returns:
        Full URL
    """
    # Remove trailing slash from base_url
    base_url = base_url.rstrip('/')

    # Ensure path starts with /
    if not path.startswith('/'):
        path = '/' + path

    return base_url + path
