import logging
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

logger = logging.getLogger("clariq.database")

db_url = settings.database_url

# Configure database engine
connect_args = {}
engine_kwargs = {
    "echo": settings.SQL_ECHO,
}

if db_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False
    engine_kwargs["connect_args"] = connect_args
else:
    # PostgreSQL / Supabase connection pooling configuration
    engine_kwargs.update({
        "pool_pre_ping": True,
        "pool_recycle": 1800,
        "pool_size": 10,
        "max_overflow": 20,
    })

engine = create_engine(db_url, **engine_kwargs)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


def get_db() -> Generator:
    """FastAPI dependency that yields an active database session and guarantees closure."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database_connection() -> dict:
    """
    Actively tests the Supabase PostgreSQL connectivity.
    Returns status dict with connectivity flag and database details.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {
            "connected": True,
            "database_type": engine.dialect.name,
            "status": "online",
        }
    except Exception as e:
        logger.error("Database health check failed: %s", str(e))
        return {
            "connected": False,
            "database_type": engine.dialect.name,
            "status": "offline",
            "error": str(e),
        }
