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


# ==================== Runtime Layer Exceptions ====================


class RuntimeException(MosaicException):
    """Base exception for all runtime layer errors

    Runtime layer exceptions are thrown by RuntimeManager and related
    components. They inherit from MosaicException so they are caught
    by the global exception handler.
    """

    def __init__(self, message: str, code: str):
        super().__init__(message, code)


class RuntimeConfigError(RuntimeException):
    """Runtime configuration error

    Examples:
        - Missing required configuration (zmq, runtime)
        - Invalid configuration values
        - Missing configuration fields
    """

    def __init__(self, message: str):
        super().__init__(message, "RUNTIME_CONFIG_ERROR")


class RuntimeAlreadyStartedError(RuntimeException):
    """RuntimeManager is already started

    Examples:
        - Attempting to start RuntimeManager twice
    """

    def __init__(self, message: str):
        super().__init__(message, "RUNTIME_ALREADY_STARTED")


class RuntimeNotStartedError(RuntimeException):
    """RuntimeManager is not started

    Examples:
        - Attempting to use RuntimeManager before starting
    """

    def __init__(self, message: str):
        super().__init__(message, "RUNTIME_NOT_STARTED")


class MosaicAlreadyRunningError(RuntimeException):
    """Mosaic instance is already running

    Examples:
        - Attempting to start a mosaic that's already running
    """

    def __init__(self, message: str):
        super().__init__(message, "MOSAIC_ALREADY_RUNNING")


class MosaicStartingError(RuntimeException):
    """Mosaic instance is currently starting

    Examples:
        - Attempting to start a mosaic that's already in startup process
        - Attempting to operate on a mosaic before startup completes
    """

    def __init__(self, message: str):
        super().__init__(message, "MOSAIC_STARTING")


class MosaicNotRunningError(RuntimeException):
    """Mosaic instance is not running

    Examples:
        - Attempting to stop a mosaic that's not running
        - Attempting to operate on nodes/sessions when mosaic is stopped
    """

    def __init__(self, message: str):
        super().__init__(message, "MOSAIC_NOT_RUNNING")


class NodeAlreadyRunningError(RuntimeException):
    """Node is already running

    Examples:
        - Attempting to start a node that's already running
    """

    def __init__(self, message: str):
        super().__init__(message, "NODE_ALREADY_RUNNING")


class NodeNotRunningError(RuntimeException):
    """Node is not running

    Examples:
        - Attempting to stop a node that's not running
        - Attempting to operate on sessions when node is stopped
    """

    def __init__(self, message: str):
        super().__init__(message, "NODE_NOT_RUNNING")


class NodeNotFoundError(RuntimeException):
    """Node not found in runtime

    Examples:
        - Node doesn't exist in mosaic instance
        - Node has been removed
    """

    def __init__(self, message: str):
        super().__init__(message, "NODE_NOT_FOUND")


class SessionNotFoundError(RuntimeException):
    """Session not found in runtime

    Examples:
        - Session doesn't exist in node
        - Session has been closed
    """

    def __init__(self, message: str):
        super().__init__(message, "SESSION_NOT_FOUND")


class SessionConflictError(RuntimeException):
    """Session already exists (conflict)

    Examples:
        - Session ID already exists in database (orphan session from crash)
        - Session ID already exists in memory
        - Attempting to create session with duplicate session_id
    """

    def __init__(self, message: str):
        super().__init__(message, "SESSION_CONFLICT")


class RuntimeTimeoutError(RuntimeException):
    """Runtime operation timeout

    Examples:
        - Mosaic startup timeout
        - Node startup timeout
        - Command execution timeout
    """

    def __init__(self, message: str):
        super().__init__(message, "RUNTIME_TIMEOUT")


class RuntimeInternalError(RuntimeException):
    """Runtime internal error (unexpected runtime failures)

    Examples:
        - Event loop not found
        - No worker threads available
        - Thread communication failure
    """

    def __init__(self, message: str):
        super().__init__(message, "RUNTIME_INTERNAL_ERROR")
