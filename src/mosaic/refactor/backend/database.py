"""Database connection and session management"""
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from .config import settings
from .logger import get_logger

# Import all models to ensure they are registered with SQLModel
from .models.user import User, EmailVerification  # noqa: F401
from .models.mosaic import Mosaic  # noqa: F401
from .models.node import Node  # noqa: F401
from .models.connection import Connection  # noqa: F401
from .models.subscription import Subscription  # noqa: F401
from .models.session import Session as SessionModel  # noqa: F401
from .models.message import Message  # noqa: F401
from .models.event import Event  # noqa: F401

logger = get_logger(__name__)

# Create sync engine for table creation
sync_engine = create_engine(
    settings.database_url,
    echo=settings.debug,
    connect_args=(
        {"check_same_thread": False}
        if settings.database_url.startswith("sqlite")
        else {}
    ),
)

# Create async engine for runtime operations
# Convert sqlite:/// to sqlite+aiosqlite:///
async_database_url = settings.database_url.replace(
    "sqlite://", "sqlite+aiosqlite://"
)
engine = create_async_engine(
    async_database_url,
    echo=settings.debug,
    connect_args=(
        {"check_same_thread": False}
        if async_database_url.startswith("sqlite")
        else {}
    ),
)

# Create async session factory
async_session_maker = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


def create_db_and_tables():
    """Create database tables (sync operation)"""
    logger.info("Creating database tables...")
    try:
        SQLModel.metadata.create_all(sync_engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")
        raise


async def get_session():
    """Get async database session (for dependency injection)"""
    async with async_session_maker() as session:
        yield session
