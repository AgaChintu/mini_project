# ClariQ — Part 1: API Reference Documentation

**Base URL:** `http://127.0.0.1:8000`  
**Authentication Scheme:** HTTP Bearer JWT (`Authorization: Bearer <token>`)

---

## 1. System Health & Diagnostics

### `GET /api/health`
Checks overall application status and active database connectivity.

**Request:**
- Method: `GET`
- Query Parameters: None
- Headers: None required

**Response (200 OK / 503 Service Unavailable if DB offline):**
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
    "type": "mysql"
  }
}
```

---

### `GET /api/health/database`
Actively runs a ping query (`SELECT 1`) to verify database responsiveness.

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Database connection verified successfully",
  "database": {
    "status": "online",
    "connected": true,
    "type": "mysql"
  }
}
```

**Error Response (503 Service Unavailable):**
```json
{
  "success": false,
  "message": "Database connection is unavailable",
  "database": {
    "status": "offline",
    "connected": false,
    "error": "Can't connect to MySQL server on '127.0.0.1' (10061)"
  }
}
```

---

## 2. Academic Hierarchy APIs

All academic endpoints return a standardized envelope:
```json
{
  "success": true,
  "message": "<Description>",
  "data": [...]
}
```

### `GET /api/academic/years`
Fetch all defined academic cohort years.

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Academic years retrieved successfully",
  "data": [
    {
      "id": 1,
      "name": "Year 1",
      "year_number": 1,
      "is_active": true,
      "created_at": "2026-11-24T09:15:35"
    },
    {
      "id": 2,
      "name": "Year 2",
      "year_number": 2,
      "is_active": true,
      "created_at": "2026-11-24T09:15:35"
    }
  ]
}
```

---

### `GET /api/academic/semesters`
Fetch academic semesters, with optional filtering by year.

**Query Parameters:**
- `academic_year_id` (optional, integer): Filter semesters by academic year.

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Semesters retrieved successfully",
  "data": [
    {
      "id": 3,
      "academic_year_id": 2,
      "semester_number": 3,
      "name": "Semester 3"
    }
  ]
}
```

---

### `GET /api/academic/sections`
Fetch student class sections.

**Query Parameters:**
- `academic_year_id` (optional, integer): Filter sections by year.
- `semester_id` (optional, integer): Filter sections by semester.

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Sections retrieved successfully",
  "data": [
    {
      "id": 7,
      "academic_year_id": 2,
      "semester_id": 3,
      "code": "AIML",
      "name": "2-AIML"
    }
  ]
}
```

---

### `GET /api/academic/subjects`
Fetch subjects offered by curriculum.

**Query Parameters:**
- `semester_id` (optional, integer): Filter subjects offered in a specific semester.
- `section_id` (optional, integer): Filter subjects offered to a specific section via section group offerings.

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Subjects retrieved successfully",
  "data": [
    {
      "id": 8,
      "code": "BCC302",
      "name": "Python Programming",
      "subject_type": "theory",
      "description": "Applied Python programming"
    }
  ]
}
```

---

### `GET /api/academic/subjects/{subject_id}/units`
Fetch syllabus units for a subject.

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Syllabus units for subject Python Programming retrieved successfully",
  "data": [
    {
      "id": 1,
      "subject_id": 8,
      "unit_number": 1,
      "unit_name": "Introduction to Python",
      "description": "Introduction to Python",
      "proposed_lectures": 8,
      "topics": null
    }
  ]
}
```

---

### `GET /api/academic/units/{unit_id}/topics`
Fetch topics belonging to a syllabus unit.

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Topics for unit Introduction to Python retrieved successfully",
  "data": [
    {
      "id": 1,
      "unit_id": 1,
      "name": "Introduction to Python and its features",
      "description": "Introduction to Python and its features",
      "display_order": 1,
      "subtopics": null
    }
  ]
}
```

---

### `GET /api/academic/topics/{topic_id}/subtopics`
Fetch granular subtopics belonging to a topic.

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Subtopics for topic 'Introduction to Python and its features' retrieved successfully",
  "data": [
    {
      "id": 1,
      "topic_id": 1,
      "name": "History of Python",
      "display_order": 1
    },
    {
      "id": 2,
      "topic_id": 1,
      "name": "Features & Advantages",
      "display_order": 2
    }
  ]
}
```

---

## 3. Authentication APIs

### `POST /api/auth/login`
Authenticates a student or teacher using their unique College ID and password.

**Request Body:**
```json
{
  "college_id": "S001",
  "password": "student123"
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user_id": 1,
  "college_id": "S001",
  "name": "Aarav Sharma",
  "role": "STUDENT"
}
```

---

### `GET /api/auth/me`
Retrieves authenticated profile details using the Bearer token.

**Headers:**
`Authorization: Bearer <token>`

**Response (200 OK):**
```json
{
  "user_id": 1,
  "college_id": "S001",
  "name": "Aarav Sharma",
  "role": "STUDENT"
}
```

---

## 4. Student Doubts APIs

### `POST /api/student/doubts/create`
Submit a new academic doubt with optional file attachments (multi-part form).

**Form Parameters:**
- `subject_id` (int, required)
- `teacher_id` (int, optional)
- `topic_id` (int, optional)
- `question` (text, required)
- `title` (string, optional)
- `description` (text, optional)
- `subtopic_ids` (comma-separated integers, optional)
- `attachments` (file, optional, up to 10 MB, allowed: PNG, JPG, PDF)

**Response (200 OK):** Returns created doubt object with `doubt_code` and `status="pending"`.

---

### `GET /api/student/doubts`
Lists all doubts submitted by the currently logged-in student.

**Headers:**
`Authorization: Bearer <token>`

---

### `GET /api/student/doubts/{doubt_code}`
Retrieves details, answers, and attachments for a specific doubt.

---

### `GET /api/student/doubts/{doubt_code}/attachments/{attachment_id}`
Securely streams an attachment file without exposing public static file paths.

---

## 5. Student Doubt Sessions APIs

### `GET /api/student/sessions`
Lists upcoming and active doubt sessions available to the authenticated student's section.

---

### `GET /api/student/sessions/{session_id}`
Retrieves session topics and doubts submitted by the current student for this session.

---

### `POST /api/student/sessions/{session_id}/doubts`
Submits a doubt for an open session window.
