# ClariQ — Supabase API Reference Documentation

**Base API URL:** `http://127.0.0.1:8000`  
**Authentication Scheme:** HTTP Bearer JWT (`Authorization: Bearer <token>`)  
**Storage Backend:** Supabase Storage (`clariq-attachments`)  

---

## 1. System Health Endpoints

### `GET /api/health`
Reports application status and active Supabase PostgreSQL connectivity.

**Response (200 OK):**
```json
{
  "success": true,
  "application_status": "healthy",
  "service": "ClariQ API",
  "version": "1.0.0",
  "environment": "development",
  "database": {
    "status": "online",
    "connected": true,
    "type": "postgresql"
  }
}
```

---

### `GET /api/health/database`
Actively runs `SELECT 1` against Supabase PostgreSQL.

---

## 2. Academic Hierarchy Endpoints

- `GET /api/academic/years`
- `GET /api/academic/semesters?academic_year_id={id}`
- `GET /api/academic/sections?academic_year_id={id}&semester_id={id}`
- `GET /api/academic/subjects?semester_id={id}&section_id={id}`
- `GET /api/academic/subjects/{subject_id}/units`
- `GET /api/academic/units/{unit_id}/topics`
- `GET /api/academic/topics/{topic_id}/subtopics`

---

## 3. Authentication Endpoints

- `POST /api/auth/login`: Authenticates Student/Teacher via College ID and password.
- `GET /api/auth/me`: Decodes JWT token and returns user profile.

---

## 4. Student Doubts Endpoints

- `POST /api/student/doubts/create`: Accepts multi-part doubt forms and uploads attachments to Supabase Storage.
- `GET /api/student/doubts`: Lists doubts for the logged-in student.
- `GET /api/student/doubts/{doubt_code}`: Details and resolution history.
- `GET /api/student/doubts/{doubt_code}/attachments/{attachment_id}`: Securely streams attachment bytes from Supabase Storage with authentication checks.

---

## 5. Student Doubt Sessions Endpoints

- `GET /api/student/sessions`: Lists active and upcoming doubt sessions.
- `GET /api/student/sessions/{session_id}`: Retrieves session details and submitted doubts.
- `POST /api/student/sessions/{session_id}/doubts`: Submits a session doubt.
