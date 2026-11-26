# ClariQ — Part 1: Backend & Database Foundation Audit Report

**Date:** 2026-11-24  
**Project:** ClariQ (Academic Doubt-Resolution & Session-Management Platform)  
**Scope:** Part 1 — Backend & Database Foundation Audit

---

## 1. Existing Project Architecture

The repository contains three primary top-level components:
- **Frontend (`frontend/`)**: Static vanilla HTML5, CSS3, and modern JavaScript (ES6+) with Lucide icons.
  - Divided into **Student Pages** (`student-pages/`, `student-css/`, `student-js/`) and **Teacher Pages** (`teacher-pages/`, `teacher-css/`, `teacher-js/`).
  - No frontend frameworks (React/Vue/Angular) are used; persistence is split between browser `sessionStorage` (for authentication token and user profile) and `localStorage` (for mocked student doubt submission, session states, and teacher views).
  - Authentication in `frontend/student-js/login.js` and session queries in `frontend/student-js/doubt-sessions.js` target a FastAPI backend at `http://127.0.0.1:8000`.
- **Primary Backend (`backend-python/`)**: Python service powered by **FastAPI**, **SQLAlchemy ORM**, **PyMySQL**, **python-jose** (JWT), and **pwdlib / Argon2**.
  - Current entry point is `app/main.py`.
  - Configured for MySQL via environment variables.
  - Exposes authentication (`/api/auth`), student doubt submission and tracking (`/api/student/doubts`), and student doubt sessions (`/api/student/sessions`).
- **Secondary Backend (`backend/`)**: Legacy/parallel Java service powered by **Spring Boot 3.x**, **Spring Data JPA**, **Hibernate**, and **Maven**.
  - Contains entities for User, Doubt, DoubtSession, ExamSupport, Notification, SavedDoubt, StudentProfile, TeacherAssignment, and Academic hierarchy.
  - Intended to connect to MySQL (`jdbc:mysql://localhost:3306/clariq_db`).
  - Kept untouched as per project instructions to avoid architecture mixing.

---

## 2. Existing Python Backend Structure

```
backend-python/
├── app/
│   ├── __init__.py
│   ├── auth_schemas.py           # Pydantic schemas for LoginRequest and LoginResponse
│   ├── database.py               # SQLAlchemy URL builder, Engine, SessionLocal, get_db dependency
│   ├── main.py                   # FastAPI app initialization, CORS middleware, table creation on startup
│   ├── security.py               # Argon2 password hashing and JWT token creation/decoding
│   ├── models/
│   │   ├── __init__.py           # Re-exports all models
│   │   ├── academic.py           # AcademicYear, Semester, SectionGroup, Section, Subject, Offerings, Syllabus
│   │   ├── assignment.py         # TeacherAssignment
│   │   ├── doubt.py              # Doubt, DoubtSubtopic, DoubtAnswer, Attachment
│   │   ├── library.py            # LibraryEntry, SavedEntry
│   │   ├── session.py            # DoubtSession, SessionTopic, SessionDoubt
│   │   └── user.py               # Student, Teacher
│   └── routers/
│       ├── __init__.py
│       ├── auth.py               # /api/auth/login, /api/auth/me
│       ├── student_doubts.py     # /api/student/doubts CRUD and file download
│       └── student_sessions.py   # /api/student/sessions endpoints
├── .env.example                  # Environment template
├── README.md                     # Setup instructions and current API coverage
├── requirements.txt              # Core Python dependencies
├── seed_data.py                  # Seeder for academic years, subjects, teachers, and Python syllabus
└── set_account_password.py       # Helper script to set test account passwords
```

---

## 3. Existing Java Backend Structure

```
backend/
├── pom.xml                       # Maven build descriptor (Spring Boot 3.3.4, Java 17)
├── src/main/java/com/clariq/backend/
│   ├── BackendApplication.java   # Spring Boot entry point
│   ├── HealthController.java     # /api/health and /api/test
│   ├── config/                   # CorsConfig, PasswordConfig, TestUserSeeder
│   ├── controller/               # Auth, Academic, Doubt, DoubtSession, ExamSupport, Library, etc.
│   ├── dto/                      # LoginRequest, LoginResponse, DoubtSessionRequest, ExamSupportRequest
│   ├── entity/                   # User, StudentProfile, Doubt, DoubtResponse, DoubtSession, etc.
│   └── repository/               # Spring Data JPA repositories
└── src/main/resources/
    └── application.properties    # Configured for jdbc:mysql://localhost:3306/clariq_db
```
*Note: The Java backend remains in place as reference and is not modified or merged into the Python runtime.*

---

## 4. Existing Database Schema & Model Analysis

The existing SQLAlchemy models in `backend-python/app/models/` map to the following MySQL tables:
1. `academic_years`: `id`, `name`, `year_number`.
2. `semesters`: `id`, `academic_year_id`, `semester_number`, `name`.
3. `section_groups`: `id`, `academic_year_id`, `code`, `name`, `description`.
4. `sections`: `id`, `academic_year_id`, `code`, `name`.
5. `section_group_members`: `id`, `section_group_id`, `section_id`.
6. `subjects`: `id`, `code`, `name`, `subject_type`, `description`.
7. `subject_offerings`: `id`, `semester_id`, `section_group_id`, `subject_id`, `lecture_hours`, `tutorial_hours`, `practical_hours`.
8. `syllabus_units`: `id`, `subject_id`, `unit_number`, `unit_name`, `proposed_lectures`.
9. `syllabus_topics`: `id`, `unit_id`, `name`, `description`, `display_order`.
10. `syllabus_subtopics`: `id`, `topic_id`, `name`, `display_order`.
11. `course_outcomes`: `id`, `subject_id`, `co_number`, `description`, `bloom_levels`.
12. `textbooks`: `id`, `subject_id`, `title`, `authors`, `publisher`, `edition`, `book_type`, `display_order`.
13. `students`: `id`, `student_code`, `full_name`, `email`, `password_hash`, `section_id`, `is_active`.
14. `teachers`: `id`, `teacher_code`, `full_name`, `email`, `password_hash`, `is_active`.
15. `teacher_assignments`: `id`, `teacher_id`, `semester_id`, `section_id`, `subject_id`.
16. `doubts`: `id`, `doubt_code`, `student_id`, `section_id`, `subject_id`, `teacher_id`, `topic_id`, `subtopic_id`, `question`, `status`, `created_at`, `updated_at`, `is_anonymous_to_teacher`.
17. `doubt_subtopics`: `id`, `doubt_id`, `subtopic_id`.
18. `doubt_answers`: `id`, `doubt_id`, `teacher_id`, `answer_text`, `resource_url`, `created_at`.
19. `attachments`: `id`, `doubt_id`, `original_filename`, `stored_filename`, `mime_type`, `file_size`, `storage_path`, `uploaded_at`.
20. `library_entries`: `id`, `doubt_id`, `published_by_teacher_id`, `published_at`.
21. `saved_entries`: `id`, `student_id`, `library_entry_id`, `saved_at`.
22. `doubt_sessions`: `id`, `teacher_id`, `section_id`, `subject_id`, `title`, `description`, `session_date`, `starts_at`, `ends_at`, `submission_opens_at`, `submission_closes_at`, `status`, `is_active`.
23. `session_topics`: `id`, `session_id`, `topic_id`.
24. `session_doubts`: `id`, `session_id`, `student_id`, `topic_id`, `question`, `created_at`, `updated_at`, `is_edited`.

---

## 5. Already Implemented Functionality

1. **JWT & Password Security**:
   - Argon2 password hashing and verification using `pwdlib`.
   - JWT access token generation and decoding using `python-jose`.
2. **Authentication API**:
   - `POST /api/auth/login` (supports student and teacher login with `college_id`).
   - `GET /api/auth/me` (decodes Bearer token and returns authenticated profile).
3. **Student Doubts API**:
   - `POST /api/student/doubts/create` with multi-part form data and file attachment handling.
   - `GET /api/student/doubts` and `GET /api/student/doubts/{doubt_code}`.
   - `GET /api/student/doubts/{doubt_code}/attachments/{attachment_id}` for authenticated file downloads.
4. **Student Doubt Sessions API**:
   - `GET /api/student/sessions` (list active and upcoming sessions).
   - `GET /api/student/sessions/{session_id}`.
   - `POST /api/student/sessions/{session_id}/doubts` (ask doubt inside a session).
   - `PUT /api/student/sessions/{session_id}/doubts/{doubt_id}` and `DELETE`.

---

## 6. Partially Implemented Functionality

1. **Database Session & Connection Management**:
   - `app/database.py` created the SQLAlchemy engine using `URL.create` and environment variables, but did not gracefully handle SQLite test overrides or standardized connection failure reporting.
2. **Academic Structure Endpoints**:
   - An ad-hoc endpoint `GET /academic-structure` exists in `app/main.py` using raw SQL, but the standard REST hierarchy endpoints (`/api/academic/years`, `/api/academic/semesters`, `/api/academic/sections`, `/api/academic/subjects`, `/api/academic/subjects/{id}/units`, etc.) required by Phase H are missing.
3. **Database Models & Relationships**:
   - Models defined foreign key columns but lacked explicit SQLAlchemy `relationship()` declarations, cascade configurations, and `back_populates`.
   - `AcademicYear` lacked `is_active` and `created_at`.
   - `SectionGroup` and `Section` lacked `semester_id`.
   - `Student` and `Teacher` lacked `created_at` and `updated_at`.
   - `TeacherAssignment` lacked `assignment_type` and `created_at`.
   - `Doubt` model had `question` but lacked `title` and `description` expected by newer frontend forms.
4. **Seed Script (`seed_data.py`)**:
   - Seeded academic structure, teachers, and Python syllabus, but was missing demo student accounts, student-to-section mappings, and full academic subtopic seeds.

---

## 7. Missing Functionality

1. **Alembic Database Migrations**:
   - No migration environment (`alembic.ini`, migration scripts) was configured; tables were generated solely through `Base.metadata.create_all()`.
2. **Standardized Health & Database Verification APIs**:
   - Missing `GET /api/health` and `GET /api/health/database` with structured status responses adhering to Phase H requirements.
3. **Modular Core Architecture**:
   - Configuration was scattered across `database.py`, `security.py`, and `student_doubts.py` rather than centralized in `app/core/config.py`.
4. **Automated Test Suite**:
   - No automated tests (`pytest`) existed for backend verification, model integrity, API responses, or idempotency.
5. **Centralized File Storage Validation Utility**:
   - Attachment logic was inlined into `student_doubts.py` without a reusable storage service enforcing MIME validation, collision-free naming, size limits, and non-public path safety.

---

## 8. Existing Bugs and Inconsistencies

1. **Frontend-Backend Contract Mismatch in Doubts**:
   - Frontend `ask-doubt.js` submits `title` and `description` (and topics/subtopics), whereas older backend models only defined a single `question` text column.
2. **Database Engine Fallback for Testing / Offline Development**:
   - If MySQL service is stopped or port 3306 is inaccessible, `database.py` threw connection errors on startup without an option for test/in-memory database fixtures.
3. **Section and Semester Relationships**:
   - `Section` had only `academic_year_id`, making filtering sections by `semester_id` indirect and reliant on custom joins.
4. **Missing Timestamps and Audit Fields**:
   - Student, teacher, and assignment tables lacked creation timestamps, preventing audit tracking.

---

## 9. Recommended Changes

1. **Introduce Centralized Core Configuration (`app/core/config.py`)**:
   - Manage all environment variables (`DATABASE_URL`, `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `SECRET_KEY`, `CORS_ORIGINS`, `UPLOAD_DIR`, `APP_ENV`).
2. **Enhance Database Models**:
   - Add missing columns (`title`, `description`, `is_active`, `created_at`, `updated_at`, `semester_id`, `assignment_type`) while retaining legacy columns (`question`) for complete backward compatibility.
   - Define bidirectional SQLAlchemy relationships with proper cascades and indexes.
3. **Initialize Alembic Migrations**:
   - Configure Alembic to point to `app.database.Base.metadata` and create repeatable migrations.
4. **Implement Foundation APIs**:
   - Add `app/routers/health.py` with `GET /api/health` and `GET /api/health/database`.
   - Add `app/routers/academic.py` with granular hierarchy endpoints and query filtering.
5. **Implement File Storage Utility (`app/services/storage.py`)**:
   - Validate extensions, MIME types, file sizes (10MB limit), and safe path storage.
6. **Improve Seed Script (`seed_data.py`)**:
   - Add demo students and comprehensive idempotent records.
7. **Create Automated Pytest Suite**:
   - Cover health checks, database connections, model constraints, academic APIs, and seed idempotency.

---

## 10. Files Created or Modified in Part 1

| Path | Status | Purpose |
| :--- | :--- | :--- |
| `docs/PART_1_BACKEND_AUDIT.md` | Created | Complete audit report of the codebase |
| `app/core/config.py` | Created | Centralized environment and settings management |
| `app/core/database.py` | Created | Engine, SessionLocal, resilient session management |
| `app/database.py` | Modified | Backward-compatibility facade pointing to core |
| `app/models/academic.py` | Modified | Added missing columns (`is_active`, `semester_id`, timestamps, relationships) |
| `app/models/user.py` | Modified | Added timestamps and relationships |
| `app/models/assignment.py` | Modified | Added `assignment_type`, `created_at`, relationships |
| `app/models/doubt.py` | Modified | Added `title`, `description`, cascade and relationship links |
| `app/models/library.py` | Modified | Added relationship links |
| `app/models/session.py` | Modified | Added relationships and constraints |
| `app/schemas/academic.py` | Created | Pydantic response models for academic hierarchy |
| `app/schemas/common.py` | Created | Standard API response envelope schemas |
| `app/services/storage.py` | Created | File storage foundation and security validation |
| `app/routers/health.py` | Created | Health check and database ping endpoints |
| `app/routers/academic.py` | Created | Academic structure hierarchy endpoints |
| `app/main.py` | Modified | Registered new routers and centralized middleware |
| `alembic.ini` | Created | Alembic configuration |
| `alembic/` | Created | Migrations directory and initial migration version |
| `seed_data.py` | Modified | Enhanced idempotent seed script with demo accounts |
| `tests/` | Created | Pytest test suite for backend verification |
| `docs/PART_1_DATABASE_SCHEMA.md` | Created | Full database schema documentation |
| `docs/PART_1_API_DOCUMENTATION.md` | Created | REST API reference documentation |
| `docs/PART_1_SETUP_GUIDE.md` | Created | Step-by-step Windows PowerShell setup guide |
