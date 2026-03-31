import os
import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

logger = logging.getLogger(__name__)

from dotenv import load_dotenv
load_dotenv()

# Database connection
DATABASE_URL = os.environ.get("DATABASE_URL")

# Make sure it's using the asyncpg driver
if DATABASE_URL and DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# SQLAlchemy declarative base
Base = declarative_base()

# Async Engine and SessionMaker
engine = None
AsyncSessionLocal = None


def _database_missing_status() -> dict:
    return {
        "configured": False,
        "connected": False,
        "detail": "DATABASE_URL is not configured.",
    }


def _ensure_engine():
    global engine, AsyncSessionLocal

    if engine is not None and AsyncSessionLocal is not None:
        return

    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )
    AsyncSessionLocal = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

async def init_db():
    """Initialize the database connection pool."""
    global engine, AsyncSessionLocal
    
    if not DATABASE_URL:
        logger.error("DATABASE_URL not found in environment variables.")
        return

    try:
        _ensure_engine()
        logger.info("Database engine initialized.")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


async def get_database_status() -> dict:
    """Return a safe summary of database readiness."""
    if not DATABASE_URL:
        return _database_missing_status()

    try:
        if engine is None or AsyncSessionLocal is None:
            await init_db()

        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

        return {
            "configured": True,
            "connected": True,
            "detail": "Database connection verified.",
        }
    except Exception as exc:
        logger.warning("Database readiness check failed: %s", exc)
        return {
            "configured": True,
            "connected": False,
            "detail": f"Database connection failed ({exc.__class__.__name__}).",
        }

async def get_db_pool():
    """Returns the engine to act as a pool (for backward compatibility in main.py)."""
    if engine is None:
        await init_db()
    
    # We return a dummy object that can be "closed" if needed, 
    # but the real disposal is engine.dispose()
    class DummyPool:
        async def close(self):
            if engine:
                await engine.dispose()
    return DummyPool()

async def get_db_session():
    """Yields a database session."""
    if AsyncSessionLocal is None:
        await init_db()

    if AsyncSessionLocal is None:
        raise RuntimeError("Database session factory is not initialized.")
        
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            raise
        finally:
            await session.close()
