"""FastAPI application entry point"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .config import settings
from .database import create_db_and_tables
from .api import (
    auth_router,
    mosaic_router,
    node_router,
    connection_router,
    subscription_router,
    workspace_router,
)
from .api.websocket import router as websocket_router
from .api.session import router as session_router
from .api.event import router as event_router
from .exceptions import MosaicException
from .logger import setup_logger, get_logger

# Setup root logger
setup_logger("mosaic.backend")
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management"""
    # Startup: Create database tables
    logger.info("Initializing database...")
    try:
        create_db_and_tables()
        logger.info("Database initialization complete")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

    # Startup: Initialize RuntimeManager
    logger.info("Initializing RuntimeManager...")
    try:
        from .runtime.manager import RuntimeManager
        runtime_manager = RuntimeManager.get_instance()
        await runtime_manager.start()
        app.state.runtime_manager = runtime_manager
        logger.info("RuntimeManager initialized successfully")
    except Exception as e:
        logger.error(f"RuntimeManager initialization failed: {e}")
        raise

    # Startup: Initialize UserMessageBroker with main event loop
    logger.info("Initializing UserMessageBroker...")
    try:
        import asyncio
        from .websocket.user_broker import user_broker
        main_loop = asyncio.get_running_loop()
        user_broker.set_main_loop(main_loop)
        logger.info("UserMessageBroker initialized successfully")
    except Exception as e:
        logger.error(f"UserMessageBroker initialization failed: {e}")
        raise

    yield

    # Shutdown: Disconnect all user WebSockets
    logger.info("Disconnecting all user WebSocket connections...")
    try:
        from .websocket.user_broker import user_broker
        await user_broker.disconnect_all_users()
        logger.info("All user WebSocket connections disconnected")
    except Exception as e:
        logger.error(f"User WebSocket cleanup failed: {e}")

    # Shutdown: Stop RuntimeManager
    logger.info("Shutting down RuntimeManager...")
    try:
        if hasattr(app.state, 'runtime_manager'):
            await app.state.runtime_manager.stop()
            logger.info("RuntimeManager stopped successfully")
    except Exception as e:
        logger.error(f"RuntimeManager shutdown failed: {e}")

    # Shutdown: Cleanup resources
    logger.info("Application shutting down")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Mosaic - Event-driven distributed multi-agent system framework"
    ),
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(MosaicException)
async def mosaic_exception_handler(
    request: Request,
    exc: MosaicException,
):
    """Handle custom exceptions"""
    logger.warning(
        f"MosaicException: {exc.message} (status: {exc.status_code})"
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )


# Register routers
app.include_router(auth_router, prefix="/api")
app.include_router(mosaic_router, prefix="/api")
app.include_router(node_router, prefix="/api")
app.include_router(connection_router, prefix="/api")
app.include_router(subscription_router, prefix="/api")
app.include_router(session_router, prefix="/api")
app.include_router(event_router, prefix="/api")
app.include_router(workspace_router, prefix="/api")
app.include_router(websocket_router, prefix="/api", tags=["WebSocket"])


# Health check
@app.get("/health", tags=["System"])
def health_check():
    """Health check endpoint"""
    return {"status": "ok", "version": settings.app_version}


# Root path
@app.get("/", tags=["System"])
def root():
    """Root endpoint"""
    return {
        "message": "Welcome to Mosaic API",
        "version": settings.app_version,
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn

    logger.info(
        f"Starting Mosaic API server (debug={settings.debug})..."
    )
    uvicorn.run(
        "mosaic.refactor.backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )
