"""
SDK Exceptions

Responsibilities:
- Define SDK-specific exception hierarchy
- Provide clear error messages for different failure scenarios
- Support error context and debugging information

All SDK exceptions inherit from MosaicSDKError base class.
"""


class MosaicSDKError(Exception):
    """
    Base exception for all SDK errors.

    All SDK-specific exceptions inherit from this class.
    This allows users to catch all SDK errors with a single except clause.

    Attributes:
        message: Error message
        details: Optional dict with additional error context
    """

    def __init__(self, message: str, details: dict = None):
        """Initialize SDK error."""
        super().__init__(message)
        self.message = message
        self.details = details or {}


class AuthenticationError(MosaicSDKError):
    """
    Authentication failed.

    Raised when:
    - Login credentials are invalid
    - JWT token is invalid or expired
    - Token refresh fails
    - User doesn't have required permissions
    """
    pass


class ConnectionError(MosaicSDKError):
    """
    Connection to backend failed.

    Raised when:
    - Network connection fails
    - Backend is unreachable
    - Mesh or node doesn't exist
    - Invalid mesh/node identifiers
    """
    pass


class SessionError(MosaicSDKError):
    """
    Session-related error.

    Raised when:
    - Session creation fails
    - Session doesn't exist
    - Session is closed or invalid
    - Cannot destroy session
    """
    pass


class ProgrammableCallError(MosaicSDKError):
    """
    Programmable call execution failed.

    Raised when:
    - Method execution fails on remote node
    - Return value doesn't match schema
    - Execution timeout
    - Invalid method parameters
    """
    pass


class NotFoundError(MosaicSDKError):
    """
    Resource not found.

    Raised when:
    - Mosaic with specified name doesn't exist
    - Node with specified ID doesn't exist
    - Session not found
    - Any other resource lookup fails
    """
    pass


class ValidationError(MosaicSDKError):
    """
    Data validation failed.

    Raised when:
    - Schema validation fails
    - Invalid parameter types
    - Missing required parameters
    - Multiple resources found when expecting unique result
    """
    pass


class TimeoutError(MosaicSDKError):
    """
    Operation timed out.

    Raised when:
    - Programmable call exceeds timeout
    - HTTP request times out
    """
    pass
