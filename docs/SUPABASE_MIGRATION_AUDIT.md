# ClariQ — Supabase PostgreSQL & Storage Migration Audit Report

**Date:** 2026-11-24  
**Project:** ClariQ (AI-Powered, Identity-Protected Academic Doubt Resolution Platform)  
**Migration Scope:** Complete Migration from MySQL to Supabase PostgreSQL & Supabase Storage  

---

## 1. Executive Summary & Objective

This audit report establishes the architectural and technical blueprint to migrate the active ClariQ Python FastAPI backend from MySQL to **Supabase PostgreSQL** and **Supabase Storage**.

The migration adheres to strict architectural boundaries:
- **No full rewrite:** Maintain existing FastAPI code, SQLAlchemy ORM patterns, and Vanilla HTML/JS frontend contracts.
- **Relational preservation:** Supabase is a managed PostgreSQL database. All 24 relational models, foreign keys, composite constraints, and cascades are preserved.
- **Driver modernization:** Transition from `PyMySQL` (`mysql+pymysql`) to `psycopg 3` (`postgresql+psycopg`).
- **Storage transformation:** Transition attachment persistence from local disk directories to the private Supabase Storage bucket `clariq-attachments` with short-lived signed URLs.
- **Authentication integrity:** Preserve custom Argon2 password hashing and ClariQ JWT token issuance; do not merge or confuse Supabase Auth JWTs with application-level ClariQ JWTs without explicit migration.
- **Java backend isolation:** The legacy Spring Boot backend in `backend/` remains untouched.

---

## 2. Supabase Project Configuration & Credentials Audit

| Parameter | Configuration Value | Target Usage |
| :--- | :--- | :--- |
| **Supabase Project URL** | `https://xkxpptzhirajzjntkrlb.supabase.co` | REST API, Supabase Storage API, client init |
| **Publishable Key** | `sb_publishable_VQNuPCj6EPq6BcaGMu3fvg_jIj-9RvJ` | Client-safe anonymous operations |
| **Secret Key** | *Local Environment Only (`SUPABASE_SECRET_KEY`)* | Backend administrative & storage operations |
| **JWKS URL** | `https://xkxpptzhirajzjntkrlb.supabase.co/auth/v1/.well-known/jwks.json` | Supabase Auth token signature verification |
| **Storage Bucket** | `clariq-attachments` | Private attachment storage |
| **Database Connection** | `DATABASE_URL` (format: `postgresql+psycopg://...`) | Direct connection or Session Pooler (port 5432 / 6543) |

> **Security Rule:** The Secret Key must never be committed to Git, logged, or exposed to the client browser. It is loaded exclusively through `backend-python/.env`.

---

## 3. Analysis of Existing SQLAlchemy Models (24 Models)

The existing codebase contains exactly 24 active SQLAlchemy models registered in `app.models`:

### A. Academic Hierarchy (12 Models)
1. `AcademicYear`: `id`, `name` (unique), `year_number` (unique), `is_active`, `created_at`.
2. `Semester`: `id`, `academic_year_id` (FK), `semester_number`, `name`. Composite unique: `(academic_year_id, semester_number)`.
3. `SectionGroup`: `id`, `academic_year_id` (FK), `semester_id` (FK), `code` (unique), `name`, `description`.
4. `Section`: `id`, `academic_year_id` (FK), `semester_id` (FK), `code`, `name`. Composite unique: `(academic_year_id, code)`.
5. `SectionGroupMember`: `id`, `section_group_id` (FK), `section_id` (FK). Composite unique: `(section_group_id, section_id)`.
6. `Subject`: `id`, `code` (unique, index), `name`, `subject_type`, `description`.
7. `SubjectOffering`: `id`, `semester_id` (FK), `section_group_id` (FK), `subject_id` (FK), `lecture_hours`, `tutorial_hours`, `practical_hours`. Composite unique: `(semester_id, section_group_id, subject_id)`.
8. `SyllabusUnit`: `id`, `subject_id` (FK), `unit_number`, `unit_name`, `description`, `proposed_lectures`. Composite unique: `(subject_id, unit_number)`.
9. `SyllabusTopic`: `id`, `unit_id` (FK), `name`, `description`, `display_order`.
10. `SyllabusSubtopic`: `id`, `topic_id` (FK), `name`, `display_order`.
11. `CourseOutcome`: `id`, `subject_id` (FK), `co_number`, `description`, `bloom_levels`. Composite unique: `(subject_id, co_number)`.
12. `Textbook`: `id`, `subject_id` (FK), `title`, `authors`, `publisher`, `edition`, `book_type`, `display_order`.

### B. User & Assignment Models (3 Models)
13. `Teacher`: `id`, `teacher_code` (unique, index), `full_name`, `email` (unique, index), `password_hash`, `is_active`, `created_at`, `updated_at`.
14. `Student`: `id`, `student_code` (unique, index), `full_name`, `email` (unique, index), `password_hash`, `section_id` (FK), `is_active`, `created_at`, `updated_at`.
15. `TeacherAssignment`: `id`, `teacher_id` (FK), `semester_id` (FK), `section_id` (FK), `subject_id` (FK), `assignment_type`, `created_at`. Composite unique: `(teacher_id, semester_id, section_id, subject_id)`.

### C. Doubt & Resolution Models (4 Models)
16. `Doubt`: `id`, `doubt_code` (UUID unique, index), `student_id` (FK), `section_id` (FK), `subject_id` (FK), `teacher_id` (FK), `topic_id` (FK), `subtopic_id` (FK), `title`, `description`, `question`, `status` (index), `is_anonymous_to_teacher`, `created_at`, `updated_at`.
17. `DoubtSubtopic`: `id`, `doubt_id` (FK), `subtopic_id` (FK). Composite unique: `(doubt_id, subtopic_id)`.
18. `DoubtAnswer`: `id`, `doubt_id` (FK), `teacher_id` (FK), `answer_text`, `resource_url`, `created_at`, `updated_at`.
19. `Attachment`: `id`, `doubt_id` (FK), `original_filename`, `stored_filename` (unique), `mime_type`, `file_size`, `storage_path`, `uploaded_at`.

### D. Knowledge Library & Sessions (5 Models)
20. `LibraryEntry`: `id`, `doubt_id` (FK, unique), `published_by_teacher_id` (FK), `published_at`.
21. `SavedEntry`: `id`, `student_id` (FK), `library_entry_id` (FK), `saved_at`. Composite unique: `(student_id, library_entry_id)`.
22. `DoubtSession`: `id`, `teacher_id` (FK), `section_id` (FK), `subject_id` (FK), `title`, `description`, `session_date`, `starts_at`, `ends_at`, `submission_opens_at`, `submission_closes_at`, `status` (index), `is_active`, `created_at`.
23. `SessionTopic`: `id`, `session_id` (FK), `topic_id` (FK). Composite unique: `(session_id, topic_id)`.
24. `SessionDoubt`: `id`, `session_id` (FK), `student_id` (FK), `topic_id` (FK), `question`, `created_at`, `updated_at`, `is_edited`.

---

## 4. PostgreSQL Dialect Compatibility Analysis

1. **Boolean Types:**
   - MySQL uses `TINYINT(1)`.
   - PostgreSQL uses native `BOOLEAN` (`true` / `false`).
   - SQLAlchemy `sa.Boolean()` maps seamlessly, but Alembic DDL scripts must define `sa.Boolean()` and server defaults as `sa.text('true')` / `sa.text('false')`.
2. **Auto-Increment Primary Keys:**
   - MySQL uses `AUTO_INCREMENT`.
   - PostgreSQL uses `SERIAL` sequences / `GENERATED BY DEFAULT AS IDENTITY`.
   - SQLAlchemy `Integer, primary_key=True` creates standard serial primary keys automatically.
3. **Foreign Key Cascade and Index Constraints:**
   - PostgreSQL requires foreign keys and composite unique constraints to be named cleanly without colliding with schema-level constraints.
   - All table constraints (`uq_year_semester`, `uq_subject_offering`, `uq_teacher_semester_section_subject`, etc.) are 100% compatible with PostgreSQL syntax.
4. **Driver Specification:**
   - Use `psycopg 3` via dialect `postgresql+psycopg://`.
   - Connection pool settings: `pool_size=10`, `max_overflow=20`, `pool_pre_ping=True`, `pool_recycle=1800`.
   - Direct connection: port `5432`.
   - Supavisor Session Pooler: port `6543` (ideal for serverless / stateless environments).

---

## 5. Storage Migration Audit: Local Disk → Supabase Storage

### Current State
Attachments are written to local disk (`backend-python/uploads/doubts/<stored_filename>`) and served directly using FastAPI `FileResponse`.

### Target State
1. **Private Bucket:** `clariq-attachments`.
2. **File Upload Flow:**
   - Student uploads attachment via `POST /api/student/doubts/create`.
   - Storage service validates extension (`.png`, `.jpg`, `.jpeg`, `.pdf`), MIME type, and file size (≤ 10 MB).
   - Backend streams file bytes directly to Supabase Storage via Supabase Python SDK using `SUPABASE_SECRET_KEY`.
   - The generated UUID filename (`<uuid>.<ext>`) and path key (`doubts/<stored_filename>`) are saved in the `attachments` PostgreSQL table.
3. **File Access Flow:**
   - `GET /api/student/doubts/{doubt_code}/attachments/{attachment_id}` checks student ownership or teacher assignment authorization.
   - Generates a short-lived signed URL (60 seconds) from Supabase Storage and returns a temporary redirect or URL payload, preventing unauthorized or direct public file scraping.

---

## 6. Authentication & Identity Protection Audit

1. **Custom JWT Preservation:**
   - ClariQ uses self-issued JWTs signed with `JWT_SECRET_KEY` (HS256) with claims: `sub`, `college_id`, `role`.
   - Frontend `login.js` expects `{ access_token, token_type: "bearer", user_id, college_id, name, role }`.
   - This contract must remain unchanged.
2. **Supabase Auth vs. ClariQ Custom Auth:**
   - The project utilizes custom Argon2 password hashes on `students` and `teachers`.
   - `SUPABASE_JWKS_URL` is retained for future or optional Supabase Auth verification, but must not overwrite custom JWT validation without an explicit account migration phase.
3. **Anonymous Doubt Protection:**
   - In `Doubt`, `is_anonymous_to_teacher = True` by default.
   - When teachers query doubt details or inbox, student identifiers (`student_id`, `student_code`, `full_name`, `email`) must remain masked.

---

## 7. Row Level Security (RLS) Strategy

Because FastAPI connects as a database role (`postgres` / `service_role`), application-level queries typically bypass PostgreSQL RLS unless switching session authorization or querying through the Supabase PostgREST Data API.

### Multi-Layer Security Architecture
1. **Layer 1: FastAPI Application Layer (Mandatory):**
   - JWT validation on every protected route.
   - Student ownership checks (`doubt.student_id == current_student.id`).
   - Teacher assignment checks (`TeacherAssignment` verification for section & subject).
   - Identity masking before returning JSON response.
2. **Layer 2: Supabase PostgreSQL RLS Policies (Defense-in-Depth):**
   - Enabled on all tables (`ALTER TABLE <table_name> ENABLE ROW LEVEL SECURITY;`).
   - Policies defined for authenticated Supabase users using JWT claims (`auth.uid()`) to prevent data leaks if tables are accessed via the Supabase Data API or client libraries.
3. **Layer 3: Supabase Storage Policies:**
   - Bucket `clariq-attachments` configured as **Private** (no public bucket access).
   - Only backend service role or signed token holders can read objects.

---

## 8. Data Migration Strategy: MySQL → Supabase PostgreSQL

A dedicated script `scripts/migrate_mysql_to_supabase.py` is required:
- Non-destructive read from MySQL.
- Insert into Supabase PostgreSQL following table dependency order:
  1. `academic_years`
  2. `semesters`
  3. `section_groups`
  4. `sections`
  5. `section_group_members`
  6. `subjects`
  7. `subject_offerings`
  8. `syllabus_units`
  9. `syllabus_topics`
  10. `syllabus_subtopics`
  11. `course_outcomes`
  12. `textbooks`
  13. `teachers`
  14. `students`
  15. `teacher_assignments`
  16. `doubts`
  17. `doubt_subtopics`
  18. `doubt_answers`
  19. `attachments`
  20. `library_entries`
  21. `saved_entries`
  22. `doubt_sessions`
  23. `session_topics`
  24. `session_doubts`
- Idempotent upserts (`ON CONFLICT DO NOTHING`) to allow repeated, safe executions.
- Post-migration record count and relationship validation.

---

## 9. Planned Files for Implementation

| Path | Purpose |
| :--- | :--- |
| `docs/SUPABASE_MIGRATION_AUDIT.md` | This audit document |
| `docs/SUPABASE_ARCHITECTURE.md` | Complete architecture design specification |
| `docs/SUPABASE_DATABASE_SCHEMA.md` | PostgreSQL schema, types, constraints, and indexes |
| `docs/SUPABASE_SETUP_GUIDE.md` | Step-by-step setup guide with PowerShell commands |
| `docs/SUPABASE_STORAGE_GUIDE.md` | Storage configuration, bucket policy, and signed URLs |
| `docs/SUPABASE_SECURITY_AND_RLS.md` | RLS definitions, roles, and identity protection audit |
| `docs/MYSQL_TO_SUPABASE_MIGRATION_GUIDE.md` | Migration runbook, backup, and rollback procedure |
| `docs/SUPABASE_API_DOCUMENTATION.md` | Full REST API reference for Supabase deployment |
| `docs/SUPABASE_FINAL_VERIFICATION.md` | Verification checklist, test outputs, and final report |
| `backend-python/requirements.txt` | Added `psycopg[binary]`, `supabase`, `httpx` |
| `backend-python/.env.example` | Updated Supabase credentials template |
| `backend-python/app/core/config.py` | Centralized Supabase URL, key, bucket, and PostgreSQL config |
| `backend-python/app/core/database.py` | Configured for PostgreSQL/psycopg engine & pooling |
| `backend-python/app/services/storage.py` | Supabase Storage SDK integration with signed URLs |
| `backend-python/alembic/versions/0002_supabase_postgresql_foundation.py` | PostgreSQL migration revision |
| `backend-python/seed_data.py` | Updated for PostgreSQL sequences and Supabase connection |
| `scripts/migrate_mysql_to_supabase.py` | Production-grade safe migration utility |
| `backend-python/tests/` | Expanded pytest suite verifying PostgreSQL and Storage |
