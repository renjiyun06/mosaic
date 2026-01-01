"""FastAPI application factory and configuration"""

from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from .logging import setup_logging
from .exception import MosaicException
from .schema.response import ErrorResponse
from .api import (
    auth_router,
    mosaic_router,
    node_router,
    connection_router,
    subscription_router,
    event_router,
    session_router,
    message_router,
)
from .api.websocket import router as websocket_router
from .runtime.manager import RuntimeManager
from .websocket import UserMessageBroker


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

    # ==================== Lifespan Context Manager ====================

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Manage application lifespan (startup and shutdown)"""
        # Startup
        # 1. Set main event loop for UserMessageBroker
        import asyncio
        app.state.user_message_broker.set_main_loop(asyncio.get_running_loop())

        # 2. Start runtime manager
        await app.state.runtime_manager.start()

        yield  # Application is running

        # Shutdown
        # 1. Disconnect all WebSocket connections
        await app.state.user_message_broker.disconnect_all_users()

        # 2. Clean up runtime manager
        await app.state.runtime_manager.stop()

    # Create FastAPI application with lifespan
    app = FastAPI(
        title="Mosaic API",
        description="Event-driven distributed multi-agent system",
        lifespan=lifespan
    )

    # ==================== Database Configuration ====================

    # Create async database engine
    db_path = instance_path / "data" / "mosaic.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"

    engine = create_async_engine(
        db_url,
        echo=False,
        future=True,
    )

    # Create async session factory
    async_session_factory = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )

    # Store in app state for dependency injection
    app.state.engine = engine
    app.state.async_session_factory = async_session_factory
    app.state.config = config
    app.state.instance_path = instance_path

    # ==================== Runtime Manager Configuration ====================

    # Create RuntimeManager singleton with dependencies
    app.state.runtime_manager = RuntimeManager.create_instance(
        async_session_factory=async_session_factory,
        config=config
    )

    # ==================== WebSocket Configuration ====================

    # Create UserMessageBroker singleton
    app.state.user_message_broker = UserMessageBroker.create_instance()

    # ==================== CORS Configuration ====================

    # Get CORS settings from config (required, no defaults)
    cors_config = config.get('cors')
    if not cors_config:
        raise ValueError("Missing required configuration: [cors]")

    allow_origins = cors_config.get('allow_origins')
    allow_credentials = cors_config.get('allow_credentials')
    allow_methods = cors_config.get('allow_methods')
    allow_headers = cors_config.get('allow_headers')

    if not all([
        allow_origins is not None,
        allow_credentials is not None,
        allow_methods is not None,
        allow_headers is not None
    ]):
        raise ValueError(
            "Missing required CORS configuration fields: "
            "allow_origins, allow_credentials, allow_methods, allow_headers"
        )

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

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle all uncaught exceptions (fallback handler)

        This is the last-resort exception handler that catches any exception
        not handled by the specific handlers above. It logs the full error
        details and returns a generic error response to the client.

        Args:
            request: The incoming request
            exc: The exception instance

        Returns:
            JSONResponse with ErrorResponse format (HTTP 200, success=false)

        Note:
            - Logs full exception details (including traceback) for debugging
            - Returns generic message to client (don't expose internal details)
            - This handler is registered AFTER specific handlers so it acts as fallback
        """
        import logging
        import traceback

        logger = logging.getLogger(__name__)

        # Log full error details for debugging (including traceback)
        logger.error(
            f"Uncaught exception in {request.method} {request.url.path}: "
            f"{exc.__class__.__name__}: {str(exc)}\n"
            f"Traceback:\n{traceback.format_exc()}"
        )

        # Return generic error to client (don't expose internal details)
        return JSONResponse(
            status_code=200,  # Keep consistent with other error responses
            content=ErrorResponse(
                message="An unexpected error occurred. Please try again later.",
                error={"code": "INTERNAL_ERROR"}
            ).model_dump()
        )

    # ==================== Router Registration ====================

    app.include_router(auth_router, prefix="/api")
    app.include_router(mosaic_router, prefix="/api")
    app.include_router(node_router, prefix="/api")
    app.include_router(connection_router, prefix="/api")
    app.include_router(subscription_router, prefix="/api")
    app.include_router(event_router, prefix="/api")
    app.include_router(session_router, prefix="/api")
    app.include_router(message_router, prefix="/api")
    app.include_router(websocket_router, prefix="/api")

    return app
