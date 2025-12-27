"""Custom exceptions for Mosaic application"""


class MosaicException(Exception):
    """Base exception for all Mosaic business errors

    All custom exceptions should inherit from this class.
    The global exception handler will catch this and return ErrorResponse.

    Attributes:
        message: Human-readable error message
        code: Error code for client-side error handling
    """

    def __init__(self, message: str, code: str):
        """Initialize Mosaic exception

        Args:
            message: Human-readable error message
            code: Error code (e.g., "VALIDATION_ERROR", "CONFLICT")
        """
        self.message = message
        self.code = code
        super().__init__(message)


class ValidationError(MosaicException):
    """Validation error (invalid input data)

    Examples:
        - Invalid username format
        - Password too short
        - Invalid email format
        - Account disabled
        - Account not verified
    """

    def __init__(self, message: str):
        super().__init__(message, "VALIDATION_ERROR")


class ConflictError(MosaicException):
    """Resource conflict error (duplicate resource)

    Examples:
        - Username already exists
        - Email already registered
        - Mosaic name already exists
        - Node ID already exists
    """

    def __init__(self, message: str):
        super().__init__(message, "CONFLICT")


class AuthenticationError(MosaicException):
    """Authentication error (invalid credentials)

    Examples:
        - Invalid username/email or password
        - Invalid or expired token
        - Current password is incorrect
    """

    def __init__(self, message: str):
        super().__init__(message, "AUTHENTICATION_ERROR")


class NotFoundError(MosaicException):
    """Resource not found error

    Examples:
        - User not found
        - Mosaic not found
        - Node not found
        - Session not found
    """

    def __init__(self, message: str):
        super().__init__(message, "NOT_FOUND")


class PermissionError(MosaicException):
    """Permission denied error (insufficient privileges)

    Examples:
        - User doesn't own this mosaic
        - Cannot delete active mosaic
        - Cannot modify read-only resource
    """

    def __init__(self, message: str):
        super().__init__(message, "PERMISSION_DENIED")


class InternalError(MosaicException):
    """Internal server error (unexpected errors)

    Examples:
        - Database connection failed
        - Failed to create directory
        - Failed to send email
        - Unexpected runtime error
    """

    def __init__(self, message: str):
        super().__init__(message, "INTERNAL_ERROR")
