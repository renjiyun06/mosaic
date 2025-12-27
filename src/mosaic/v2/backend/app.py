"""FastAPI application instance and configuration"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from .exception import MosaicException
from .schema.response import ErrorResponse
from .api import auth_router


# Create FastAPI application
app = FastAPI(
    title="Mosaic API",
    description="Event-driven distributed multi-agent system",
    version="2.0.0",
)


# ==================== CORS Configuration ====================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],  # Frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
