# ClariQ — Part 1: Database Architecture & Schema Specification

**System:** ClariQ Academic Doubt-Resolution & Session-Management Platform  
**Database Dialect:** MySQL 8.0+ (InnoDB Engine) / SQLAlchemy 2.0+  
**CharSet / Collation:** `utf8mb4` / `utf8mb4_unicode_ci`

---

## 1. Academic Hierarchy Architecture

ClariQ enforces a strict academic hierarchy to model institutional programs, courses, syllabus units, and teacher assignments:

```
Academic Year (1, 2)
  └── Semester (1, 2, 3, 4)
        └── Section Group (e.g., Y2_COMMON)
              ├── Sections (AIML, CS1, CS2, CS3, IT, DS)
              │     └── Students (enrolled per section)
              └── Subject Offerings (Semester + Section Group)
                    └── Subjects (BCS301, BCC302, etc.)
                          ├── Syllabus Units (Unit 1 to 5)
                          │     └── Syllabus Topics
                          │           └── Syllabus Subtopics
                          └── Teacher Assignments (Teacher + Subject + Section + Semester)
```

---

## 2. Table Specifications

### A. Academic Hierarchy

#### 1. `academic_years`
Represents an academic cohort year (e.g. First Year, Second Year).

| Column | Type | Nullable | Key / Constraint | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INT` | No | PK, Auto Increment | Primary identifier |
| `name` | `VARCHAR(50)` | No | UNIQUE | Academic year name (e.g. "Year 1", "Year 2") |
| `year_number` | `INT` | No | UNIQUE | Year ordinal (1, 2, 3, 4) |
| `is_active` | `TINYINT(1)` | No | Default `1` | Active state flag |
| `created_at` | `DATETIME` | No | Default `NOW()` | Audit creation timestamp |

*Relationships:*
- Has many `semesters` (`CASCADE` delete).
- Has many `sections` (`CASCADE` delete).
- Has many `section_groups` (`CASCADE` delete).

---

#### 2. `semesters`
Semesters belonging to an academic year.

| Column | Type | Nullable | Key / Constraint | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INT` | No | PK, Auto Increment | Primary identifier |
| `academic_year_id` | `INT` | No | FK → `academic_years.id` (`CASCADE`) | Cohort year reference |
| `semester_number` | `INT` | No | Composite Unique (`academic_year_id`, `semester_number`) | Semester index (1 to 8) |
| `name` | `VARCHAR(50)` | No | | Semester name (e.g. "Semester III") |

*Relationships:*
- Belongs to `academic_years`.
- Has many `sections`.
- Has many `subject_offerings`.

---

#### 3. `section_groups`
Aggregates multiple student sections sharing common curriculum or offerings.

| Column | Type | Nullable | Key / Constraint | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INT` | No | PK, Auto Increment | Primary identifier |
| `academic_year_id` | `INT` | No | FK → `academic_years.id` (`CASCADE`) | Academic year |
| `semester_id` | `INT` | Yes | FK → `semesters.id` (`SET NULL`) | Associated semester |
| `code` | `VARCHAR(50)` | No | UNIQUE | Group code (e.g. `Y2_COMMON`) |
| `name` | `VARCHAR(100)` | No | | Group display name |
| `description` | `TEXT` | Yes | | Scope description |

*Relationships:*
- Has many `section_group_members` (`CASCADE`).
- Has many `subject_offerings` (`CASCADE`).

---

#### 4. `sections`
Specific class cohorts to which students are assigned.

| Column | Type | Nullable | Key / Constraint | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INT` | No | PK, Auto Increment | Primary identifier |
| `academic_year_id` | `INT` | No | FK → `academic_years.id` (`CASCADE`) | Academic year |
| `semester_id` | `INT` | Yes | FK → `semesters.id` (`SET NULL`) | Current semester |
| `code` | `VARCHAR(30)` | No | Composite Unique (`academic_year_id`, `code`) | Section code (`AIML`, `CS1`) |
| `name` | `VARCHAR(100)` | No | | Full name (`Year 2 - AIML`) |

---

#### 5. `section_group_members`
Many-to-many bridge mapping sections into section groups.

| Column | Type | Nullable | Key / Constraint | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INT` | No | PK, Auto Increment | Primary identifier |
| `section_group_id` | `INT` | No | FK → `section_groups.id` (`CASCADE`) | Section group |
| `section_id` | `INT` | No | FK → `sections.id` (`CASCADE`) | Section member |

*Constraints:* `UNIQUE(section_group_id, section_id)`

---

#### 6. `subjects`
Course catalogue definitions.

| Column | Type | Nullable | Key / Constraint | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INT` | No | PK, Auto Increment | Primary identifier |
| `code` | `VARCHAR(30)` | Yes | UNIQUE, INDEX | Course code (e.g., `BCC302`) |
| `name` | `VARCHAR(150)` | No | | Course title |
| `subject_type` | `VARCHAR(30)` | Yes | | `theory` / `lab` / `project` |
| `description` | `TEXT` | Yes | | Subject description |

---

#### 7. `subject_offerings`
Active curriculum offering mapping subjects to semesters and section groups.

| Column | Type | Nullable | Key / Constraint | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INT` | No | PK, Auto Increment | Primary identifier |
| `semester_id` | `INT` | No | FK → `semesters.id` (`CASCADE`) | Semester |
| `section_group_id` | `INT` | No | FK → `section_groups.id` (`CASCADE`) | Section group |
| `subject_id` | `INT` | No | FK → `subjects.id` (`CASCADE`) | Offered subject |
| `lecture_hours` | `INT` | Yes | | Weekly lecture hours (L) |
| `tutorial_hours` | `INT` | Yes | | Weekly tutorial hours (T) |
| `practical_hours` | `INT` | Yes | | Weekly practical hours (P) |

*Constraints:* `UNIQUE(semester_id, section_group_id, subject_id)`

---

#### 8. `syllabus_units`
Curricular units for an academic subject.

| Column | Type | Nullable | Key / Constraint | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INT` | No | PK, Auto Increment | Primary identifier |
| `subject_id` | `INT` | No | FK → `subjects.id` (`CASCADE`) | Parent subject |
| `unit_number` | `INT` | No | | Unit index (1 to 5) |
| `unit_name` | `VARCHAR(255)` | No | | Unit heading |
| `description` | `TEXT` | Yes | | Unit coverage summary |
| `proposed_lectures`| `INT` | Yes | | Planned lecture count |

*Constraints:* `UNIQUE(subject_id, unit_number)`

---

#### 9. `syllabus_topics`
Individual topics within a syllabus unit.

| Column | Type | Nullable | Key / Constraint | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INT` | No | PK, Auto Increment | Primary identifier |
| `unit_id` | `INT` | No | FK → `syllabus_units.id` (`CASCADE`) | Parent unit |
| `name` | `VARCHAR(255)` | No | | Topic name |
| `description` | `TEXT` | Yes | | Detailed summary |
| `display_order` | `INT` | No | Default `1` | Order of presentation |

---

#### 10. `syllabus_subtopics`
Granular concepts within a syllabus topic.

| Column | Type | Nullable | Key / Constraint | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INT` | No | PK, Auto Increment | Primary identifier |
| `topic_id` | `INT` | No | FK → `syllabus_topics.id` (`CASCADE`) | Parent topic |
| `name` | `VARCHAR(255)` | No | | Subtopic concept |
| `display_order` | `INT` | No | Default `1` | Order of presentation |

---

### B. User & Assignment Models

#### 11. `teachers`
Teacher master records.

| Column | Type | Nullable | Key / Constraint | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INT` | No | PK, Auto Increment | Primary identifier |
| `teacher_code` | `VARCHAR(50)` | No | UNIQUE, INDEX | College teacher ID (`T001`) |
| `full_name` | `VARCHAR(150)` | No | | Full name |
| `email` | `VARCHAR(255)` | Yes | UNIQUE, INDEX | Email address |
| `password_hash` | `VARCHAR(255)` | Yes | | Argon2 password hash |
| `is_active` | `TINYINT(1)` | No | Default `1` | Active flag |
| `created_at` | `DATETIME` | No | Default `NOW()` | Registration timestamp |
| `updated_at` | `DATETIME` | Yes | | Last update timestamp |

---

#### 12. `students`
Student master records.

| Column | Type | Nullable | Key / Constraint | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INT` | No | PK, Auto Increment | Primary identifier |
| `student_code` | `VARCHAR(50)` | No | UNIQUE, INDEX | College student ID (`S001`) |
| `full_name` | `VARCHAR(150)` | No | | Full name |
| `email` | `VARCHAR(255)` | Yes | UNIQUE, INDEX | Email address |
| `password_hash` | `VARCHAR(255)` | Yes | | Argon2 password hash |
| `section_id` | `INT` | No | FK → `sections.id` (`RESTRICT`) | Enrolled student section |
| `is_active` | `TINYINT(1)` | No | Default `1` | Active flag |
| `created_at` | `DATETIME` | No | Default `NOW()` | Registration timestamp |
| `updated_at` | `DATETIME` | Yes | | Last update timestamp |

---

#### 13. `teacher_assignments`
Establishes which teacher teaches which subject to which section in a semester.

| Column | Type | Nullable | Key / Constraint | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INT` | No | PK, Auto Increment | Primary identifier |
| `teacher_id` | `INT` | No | FK → `teachers.id` (`CASCADE`) | Assigned teacher |
| `semester_id` | `INT` | No | FK → `semesters.id` (`CASCADE`) | Semester |
| `section_id` | `INT` | No | FK → `sections.id` (`CASCADE`) | Target section |
| `subject_id` | `INT` | No | FK → `subjects.id` (`CASCADE`) | Assigned subject |
| `assignment_type` | `VARCHAR(50)` | Yes | Default `primary` | Role (`primary`, `lab_assistant`) |
| `created_at` | `DATETIME` | No | Default `NOW()` | Assignment date |

*Constraints:* `UNIQUE(teacher_id, semester_id, section_id, subject_id)`

---

### C. Doubt & Resolution Models

#### 14. `doubts`
Student doubts. Student identity is protected by default.

| Column | Type | Nullable | Key / Constraint | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INT` | No | PK, Auto Increment | Internal identifier |
| `doubt_code` | `VARCHAR(36)` | No | UNIQUE, INDEX | Public UUID doubt token |
| `student_id` | `INT` | No | FK → `students.id` (`CASCADE`) | Submitting student |
| `section_id` | `INT` | No | FK → `sections.id` (`RESTRICT`) | Student section |
| `subject_id` | `INT` | No | FK → `subjects.id` (`RESTRICT`) | Academic subject |
| `teacher_id` | `INT` | Yes | FK → `teachers.id` (`SET NULL`) | Direct teacher assignment |
| `topic_id` | `INT` | Yes | FK → `syllabus_topics.id` (`SET NULL`)| Optional primary topic |
| `subtopic_id` | `INT` | Yes | FK → `syllabus_subtopics.id` (`SET NULL`)| Optional primary subtopic |
| `title` | `VARCHAR(255)` | Yes | | Modern brief title |
| `description` | `TEXT` | Yes | | Modern detailed question description |
| `question` | `TEXT` | No | | Legacy compatibility question content |
| `status` | `VARCHAR(30)` | No | INDEX, Default `pending` | `pending`, `in_progress`, `resolved` |
| `is_anonymous_to_teacher` | `TINYINT(1)` | No | Default `1` | Identity protection flag |
| `created_at` | `DATETIME` | No | Default `NOW()` | Submission timestamp |
| `updated_at` | `DATETIME` | Yes | | Modification timestamp |

---

#### 15. `doubt_subtopics`
Many-to-many relationship mapping multiple syllabus subtopics to a doubt.

| Column | Type | Nullable | Key / Constraint | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INT` | No | PK, Auto Increment | Primary identifier |
| `doubt_id` | `INT` | No | FK → `doubts.id` (`CASCADE`) | Doubt reference |
| `subtopic_id` | `INT` | No | FK → `syllabus_subtopics.id` (`CASCADE`) | Subtopic tag |

*Constraints:* `UNIQUE(doubt_id, subtopic_id)`

---

#### 16. `doubt_answers`
Teacher responses and solutions. Preserves full history.

| Column | Type | Nullable | Key / Constraint | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INT` | No | PK, Auto Increment | Primary identifier |
| `doubt_id` | `INT` | No | FK → `doubts.id` (`CASCADE`) | Solved doubt |
| `teacher_id` | `INT` | No | FK → `teachers.id` (`RESTRICT`) | Responding teacher |
| `answer_text` | `TEXT` | No | | Resolution text |
| `resource_url` | `VARCHAR(1000)`| Yes | | Optional reference link |
| `created_at` | `DATETIME` | No | Default `NOW()` | Answer timestamp |
| `updated_at` | `DATETIME` | Yes | | Modification timestamp |

---

#### 17. `attachments`
Non-public file attachments (images, PDFs) linked to doubts.

| Column | Type | Nullable | Key / Constraint | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INT` | No | PK, Auto Increment | Primary identifier |
| `doubt_id` | `INT` | No | FK → `doubts.id` (`CASCADE`) | Associated doubt |
| `original_filename`| `VARCHAR(255)`| No | | Client filename |
| `stored_filename` | `VARCHAR(255)`| No | UNIQUE | UUID-based storage filename |
| `mime_type` | `VARCHAR(100)`| No | | MIME type (`image/png`, etc.) |
| `file_size` | `INT` | No | | File size in bytes (max 10MB) |
| `storage_path` | `VARCHAR(1000)`| No | | Path on disk outside public web root |
| `uploaded_at` | `DATETIME` | No | Default `NOW()` | Upload timestamp |

---

### D. Library & Doubt Session Models

#### 18. `library_entries`
Published knowledge base entries curated by teachers from resolved doubts.

| Column | Type | Nullable | Key / Constraint | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INT` | No | PK, Auto Increment | Primary identifier |
| `doubt_id` | `INT` | No | FK → `doubts.id` (`CASCADE`), UNIQUE | Resolved doubt reference |
| `published_by_teacher_id`| `INT` | No | FK → `teachers.id` (`RESTRICT`) | Curating teacher |
| `published_at` | `DATETIME` | No | Default `NOW()` | Publication date |

---

#### 19. `saved_entries`
Student bookmarks for library entries.

| Column | Type | Nullable | Key / Constraint | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INT` | No | PK, Auto Increment | Primary identifier |
| `student_id` | `INT` | No | FK → `students.id` (`CASCADE`) | Student bookmarker |
| `library_entry_id` | `INT` | No | FK → `library_entries.id` (`CASCADE`)| Saved library entry |
| `saved_at` | `DATETIME` | No | Default `NOW()` | Bookmark timestamp |

*Constraints:* `UNIQUE(student_id, library_entry_id)`

---

#### 20. `doubt_sessions`
Live or scheduled doubt resolution sessions conducted by teachers.

| Column | Type | Nullable | Key / Constraint | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INT` | No | PK, Auto Increment | Primary identifier |
| `teacher_id` | `INT` | No | FK → `teachers.id` (`CASCADE`) | Session host teacher |
| `section_id` | `INT` | No | FK → `sections.id` (`RESTRICT`) | Target section |
| `subject_id` | `INT` | No | FK → `subjects.id` (`RESTRICT`) | Target course |
| `title` | `VARCHAR(255)` | No | | Session title |
| `description` | `TEXT` | Yes | | Session instructions |
| `session_date` | `DATETIME` | Yes | | Scheduled date |
| `starts_at` | `DATETIME` | Yes | | Session start |
| `ends_at` | `DATETIME` | Yes | | Session end |
| `submission_opens_at`| `DATETIME` | No | | Window opening time |
| `submission_closes_at`| `DATETIME`| No | | Window closing time |
| `status` | `VARCHAR(30)` | No | INDEX, Default `upcoming` | `upcoming`, `active`, `completed` |
| `is_active` | `TINYINT(1)` | No | Default `1` | Active flag |
| `created_at` | `DATETIME` | No | Default `NOW()` | Creation timestamp |

---

#### 21. `session_topics`
Topics scheduled for coverage in a doubt session.

| Column | Type | Nullable | Key / Constraint | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INT` | No | PK, Auto Increment | Primary identifier |
| `session_id` | `INT` | No | FK → `doubt_sessions.id` (`CASCADE`) | Doubt session |
| `topic_id` | `INT` | No | FK → `syllabus_topics.id` (`CASCADE`)| Covered topic |

*Constraints:* `UNIQUE(session_id, topic_id)`

---

#### 22. `session_doubts`
Doubts submitted specifically for a session (isolated from general doubts).

| Column | Type | Nullable | Key / Constraint | Description |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `INT` | No | PK, Auto Increment | Primary identifier |
| `session_id` | `INT` | No | FK → `doubt_sessions.id` (`CASCADE`) | Target session |
| `student_id` | `INT` | No | FK → `students.id` (`CASCADE`) | Student submitter |
| `topic_id` | `INT` | No | FK → `syllabus_topics.id` (`RESTRICT`)| Relevant topic |
| `question` | `TEXT` | No | | Doubt question text |
| `created_at` | `DATETIME` | No | Default `NOW()` | Submission timestamp |
| `updated_at` | `DATETIME` | Yes | | Edit timestamp |
| `is_edited` | `TINYINT(1)` | No | Default `0` | Edit indicator |

---

## 3. Database Indexes

To maintain high query performance across doubt searches, auth lookups, and academic hierarchy filtering, the following indexes are defined:

1. `ix_academic_years_id` on `academic_years(id)`
2. `ix_semesters_id` on `semesters(id)`
3. `ix_section_groups_id` on `section_groups(id)`
4. `ix_sections_id` on `sections(id)`
5. `ix_subjects_code` on `subjects(code)`
6. `ix_students_student_code` on `students(student_code)`
7. `ix_students_email` on `students(email)`
8. `ix_teachers_teacher_code` on `teachers(teacher_code)`
9. `ix_teachers_email` on `teachers(email)`
10. `ix_doubts_doubt_code` on `doubts(doubt_code)`
11. `ix_doubts_status` on `doubts(status)`
12. `ix_doubt_sessions_status` on `doubt_sessions(status)`
