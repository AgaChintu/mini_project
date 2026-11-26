import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import settings
from app.core.database import engine, Base, check_database_connection
from app.core.exceptions import ClariQException, FileValidationError, EntityNotFoundError
import app.models

from app.routers.health import router as health_router
from app.routers.academic import router as academic_router
from app.routers.auth import router as auth_router
from app.routers.student_sessions import router as student_sessions_router
from app.routers.student_doubts import router as student_doubts_router
from app.routers.student_dashboard import router as student_dashboard_router
from app.routers.teacher_dashboard import router as teacher_dashboard_router
from app.routers.subject_management import router as subject_management_router
from app.routers.admin import router as admin_router
from app.routers.admin_subjects import router as admin_subjects_router
from app.routers.library import router as library_router
from app.routers.copilot import router as copilot_router
from app.routers.chatbot import router as chatbot_router

logger = logging.getLogger("clariq.app")


def bootstrap_super_admin():
    """Initializes the initial Super Admin account idempotently if none exists."""
    from app.core.database import SessionLocal
    from app.models.admin import Admin
    from app.security import hash_password

    db = SessionLocal()
    try:
        admin_count = db.query(Admin).count()
        if admin_count == 0:
            super_admin = Admin(
                username="admin",
                full_name=settings.ADMIN_INITIAL_NAME,
                email=settings.ADMIN_LOGIN_ID,
                password_hash=hash_password(settings.ADMIN_INITIAL_PASSWORD),
                is_active=True,
            )
            db.add(super_admin)
            db.commit()
            logger.info("Super Admin bootstrap account initialized successfully.")
    except Exception as e:
        logger.warning("Super Admin bootstrap skipped or failed: %s", e)
        db.rollback()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Model imports register all mapped tables before create_all
    Base.metadata.create_all(bind=engine)
    bootstrap_super_admin()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    description="Identity-protected academic doubt resolution API for students and teachers.",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# CORS configuration restricted to authorized origins and localhost regex
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:[0-9]+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers for centralized error handling and security
@app.exception_handler(ClariQException)
async def handle_clariq_exception(request: Request, exc: ClariQException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "message": exc.message, "data": None},
    )


@app.exception_handler(Exception)
async def handle_generic_exception(request: Request, exc: Exception):
    logger.error("Unhandled exception: %s", str(exc), exc_info=True)
    message = "An internal server error occurred" if settings.APP_ENV == "production" else str(exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"success": False, "message": message, "data": None},
    )


# Register API Routers
app.include_router(health_router)
app.include_router(academic_router)
app.include_router(auth_router)
app.include_router(student_sessions_router)
app.include_router(student_doubts_router)
app.include_router(student_dashboard_router)
app.include_router(teacher_dashboard_router)
app.include_router(subject_management_router)
app.include_router(admin_router)
app.include_router(admin_subjects_router)
app.include_router(library_router)
app.include_router(copilot_router)
app.include_router(chatbot_router)


# Legacy & convenience endpoints preserved for backward compatibility
@app.get("/", tags=["System"])
def home():
    return {
        "message": "ClariQ Backend is running!",
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }


@app.get("/health", tags=["System"])
def legacy_health():
    """Legacy health check endpoint alias."""
    db_status = check_database_connection()
    return {
        "status": "ok" if db_status["connected"] else "degraded",
        "service": "clariq-api",
        "database": db_status["status"],
    }


@app.get("/db-test", tags=["System"])
def test_database():
    """Legacy db-test endpoint alias."""
    db_status = check_database_connection()
    if not db_status["connected"]:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "message": db_status.get("error", "Database connection failed")},
        )
    return {"status": "success", "message": "Database connection successful."}


@app.get("/tables", tags=["System"])
def list_tables():
    return {"tables": sorted(Base.metadata.tables.keys())}


@app.get("/academic-structure", tags=["Academic"])
def get_academic_structure():
    """Legacy aggregate academic structure endpoint."""
    query = text("""
        SELECT
            ay.id AS year_id, ay.name AS year_name, ay.year_number,
            sem.id AS semester_id, sem.semester_number, sem.name AS semester_name,
            sec.id AS section_id, sec.code AS section_code, sec.name AS section_name,
            sub.id AS subject_id, sub.code AS subject_code, sub.name AS subject_name,
            sub.subject_type
        FROM academic_years ay
        LEFT JOIN semesters sem ON sem.academic_year_id = ay.id
        LEFT JOIN section_groups sg ON sg.academic_year_id = ay.id
        LEFT JOIN section_group_members sgm ON sgm.section_group_id = sg.id
        LEFT JOIN sections sec ON sec.id = sgm.section_id
        LEFT JOIN subject_offerings so
            ON so.semester_id = sem.id AND so.section_group_id = sg.id
        LEFT JOIN subjects sub ON sub.id = so.subject_id
        ORDER BY ay.year_number, sem.semester_number, sec.code, sub.name
    """)
    with engine.connect() as connection:
        rows = connection.execute(query).mappings().all()

    years = {}
    for row in rows:
        year_id = row["year_id"]
        year = years.setdefault(year_id, {
            "id": year_id,
            "name": row["year_name"],
            "year_number": row["year_number"],
            "semesters": {},
        })
        if row["semester_id"] is None:
            continue
        semester_id = row["semester_id"]
        semester = year["semesters"].setdefault(semester_id, {
            "id": semester_id,
            "semester_number": row["semester_number"],
            "name": row["semester_name"],
            "sections": {},
        })
        if row["section_id"] is None:
            continue
        section_id = row["section_id"]
        section = semester["sections"].setdefault(section_id, {
            "id": section_id,
            "code": row["section_code"],
            "name": row["section_name"],
            "subjects": {},
        })
        if row["subject_id"] is not None:
            section["subjects"][row["subject_id"]] = {
                "id": row["subject_id"],
                "code": row["subject_code"],
                "name": row["subject_name"],
                "subject_type": row["subject_type"],
            }

    result = []
    for year in years.values():
        semesters = []
        for semester in year["semesters"].values():
            sections = []
            for section in semester["sections"].values():
                section["subjects"] = list(section["subjects"].values())
                sections.append(section)
            semester["sections"] = sections
            semesters.append(semester)
        year["semesters"] = semesters
        result.append(year)
    return {"academic_years": result}
