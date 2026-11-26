from fastapi import APIRouter, Depends, status, Response
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db, check_database_connection

router = APIRouter(prefix="/api/health", tags=["System Health"])


@router.get("", status_code=status.HTTP_200_OK)
def get_health_status(response: Response):
    """
    Returns application and database connectivity status.
    Does not expose sensitive credentials, internal secrets, or raw connection strings.
    """
    db_status = check_database_connection()
    is_healthy = db_status["connected"]

    if not is_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "success": is_healthy,
        "application_status": "healthy" if is_healthy else "degraded",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "database": {
            "status": db_status["status"],
            "connected": db_status["connected"],
            "type": db_status.get("database_type", "unknown"),
        },
    }


@router.get("/database")
@router.get("/db")
def get_database_health(response: Response):
    """
    Actively checks the database connection by executing a verification query.
    Returns 200 on success, or 503 if unavailable.
    """
    db_status = check_database_connection()
    if not db_status["connected"]:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "success": False,
            "message": "Database connection is unavailable",
            "database": {
                "status": "offline",
                "connected": False,
                "error": db_status.get("error", "Unknown database error"),
            },
        }

    return {
        "success": True,
        "message": "Database connection verified successfully",
        "database": {
            "status": "online",
            "connected": True,
            "type": db_status.get("database_type"),
        },
    }
