"""
Database module facade.
Maintains backward compatibility with all existing imports referencing app.database.
"""

from app.core.database import (
    engine,
    SessionLocal,
    Base,
    get_db,
    check_database_connection,
)
from app.core.config import settings

# Backward compatible attribute exports
DATABASE_URL = settings.database_url
DB_HOST = settings.DB_HOST
DB_PORT = settings.DB_PORT
DB_NAME = settings.DB_NAME
DB_USER = settings.DB_USER
DB_PASSWORD = settings.DB_PASSWORD
