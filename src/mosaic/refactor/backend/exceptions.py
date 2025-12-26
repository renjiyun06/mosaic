"""Custom exceptions"""


class MosaicException(Exception):
    """Base Mosaic exception"""

    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class AuthenticationError(MosaicException):
    """Authentication error"""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, status_code=401)


class AuthorizationError(MosaicException):
    """Authorization error"""

    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(message, status_code=403)


class NotFoundError(MosaicException):
    """Resource not found error"""

    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, status_code=404)


class ValidationError(MosaicException):
    """Data validation error"""

    def __init__(self, message: str = "Validation failed"):
        super().__init__(message, status_code=422)


class ConflictError(MosaicException):
    """Resource conflict error"""

    def __init__(self, message: str = "Resource conflict"):
        super().__init__(message, status_code=409)


class RuntimeOperationError(MosaicException):
    """Runtime operation error (e.g., mosaic not running, node not started)"""

    def __init__(self, message: str = "Runtime operation failed"):
        super().__init__(message, status_code=400)
