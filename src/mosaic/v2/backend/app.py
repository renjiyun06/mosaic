"""FastAPI application factory and configuration"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from .logging import setup_logging
from .exception import MosaicException
from .schema.response import ErrorResponse
from .api import auth_router


def create_app(instance_path: Path, config: dict) -> FastAPI:
    """Create and configure FastAPI application instance

    This is the application factory function that initializes logging,
    creates the FastAPI app, configures middleware, registers exception
    handlers, and includes routers.

    Args:
        instance_path: Path to the Mosaic instance directory
        config: Configuration dictionary loaded from config.toml

    Returns:
        Configured FastAPI application instance
    """
    # Initialize logging first
    setup_logging(instance_path)

    # Create FastAPI application
    app = FastAPI(
        title="Mosaic API",
        description="Event-driven distributed multi-agent system",
    )

    # ==================== CORS Configuration ====================

    # Get CORS settings from config (required, no defaults)
    cors_config = config.get('cors', {})
    allow_origins = cors_config.get('allow_origins', [])
    allow_credentials = cors_config.get('allow_credentials', True)
    allow_methods = cors_config.get('allow_methods', ["*"])
    allow_headers = cors_config.get('allow_headers', ["*"])

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=allow_credentials,
        allow_methods=allow_methods,
        allow_headers=allow_headers,
    )

    # ==================== Exception Handlers ====================

    @app.exception_handler(MosaicException)
    async def mosaic_exception_handler(request: Request, exc: MosaicException) -> JSONResponse:
        """Handle all Mosaic business exceptions

        All custom exceptions (ValidationError, ConflictError, etc.) inherit from MosaicException.
        This handler catches them and returns a unified ErrorResponse format.

        Args:
            request: The incoming request
            exc: The Mosaic exception instance

        Returns:
            JSONResponse with ErrorResponse format (HTTP 200, success=false)
        """
        return JSONResponse(
            status_code=200,  # Business errors return 200 with success=false
            content=ErrorResponse(
                message=exc.message,
                error={"code": exc.code}
            ).model_dump()
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        """Handle Pydantic validation errors

        This catches errors from FastAPI's automatic request validation
        (e.g., invalid email format, missing required fields, type mismatches).

        Args:
            request: The incoming request
            exc: The validation error instance

        Returns:
            JSONResponse with ErrorResponse format (HTTP 200, success=false)
        """
        return JSONResponse(
            status_code=200,  # Validation errors also return 200 with success=false
            content=ErrorResponse(
                message="Invalid input format",
                error={
                    "code": "VALIDATION_ERROR",
                    "details": exc.errors()
                }
            ).model_dump()
        )

    # ==================== Router Registration ====================

    app.include_router(auth_router, prefix="/api")

    return app
