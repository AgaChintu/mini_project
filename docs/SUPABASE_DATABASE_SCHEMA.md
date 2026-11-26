# ClariQ — Supabase PostgreSQL Database Schema

**Dialect:** Supabase PostgreSQL 15+  
**ORM:** SQLAlchemy 2.0  
**Driver:** `psycopg` 3 (`postgresql+psycopg`)  

---

## 1. Table Definitions & Relational Schema

### A. Academic Hierarchy
1. **`academic_years`**
   - `id`: `INTEGER` (PK, Serial)
   - `name`: `VARCHAR(50)` (UNIQUE, NOT NULL)
   - `year_number`: `INTEGER` (UNIQUE, NOT NULL)
   - `is_active`: `BOOLEAN` (NOT NULL, DEFAULT `true`)
   - `created_at`: `TIMESTAMP WITHOUT TIME ZONE` (DEFAULT `NOW()`)

2. **`semesters`**
   - `id`: `INTEGER` (PK, Serial)
   - `academic_year_id`: `INTEGER` (FK → `academic_years.id` ON DELETE CASCADE)
   - `semester_number`: `INTEGER` (NOT NULL)
   - `name`: `VARCHAR(50)` (NOT NULL)
   - *Constraint:* `UNIQUE (academic_year_id, semester_number)`

3. **`section_groups`**
   - `id`: `INTEGER` (PK, Serial)
   - `academic_year_id`: `INTEGER` (FK → `academic_years.id` ON DELETE CASCADE)
   - `semester_id`: `INTEGER` (FK → `semesters.id` ON DELETE SET NULL)
   - `code`: `VARCHAR(50)` (UNIQUE, NOT NULL)
   - `name`: `VARCHAR(100)` (NOT NULL)
   - `description`: `TEXT`

4. **`sections`**
   - `id`: `INTEGER` (PK, Serial)
   - `academic_year_id`: `INTEGER` (FK → `academic_years.id` ON DELETE CASCADE)
   - `semester_id`: `INTEGER` (FK → `semesters.id` ON DELETE SET NULL)
   - `code`: `VARCHAR(30)` (NOT NULL)
   - `name`: `VARCHAR(100)` (NOT NULL)
   - *Constraint:* `UNIQUE (academic_year_id, code)`

5. **`section_group_members`**
   - `id`: `INTEGER` (PK, Serial)
   - `section_group_id`: `INTEGER` (FK → `section_groups.id` ON DELETE CASCADE)
   - `section_id`: `INTEGER` (FK → `sections.id` ON DELETE CASCADE)
   - *Constraint:* `UNIQUE (section_group_id, section_id)`

6. **`subjects`**
   - `id`: `INTEGER` (PK, Serial)
   - `code`: `VARCHAR(30)` (UNIQUE, INDEX)
   - `name`: `VARCHAR(150)` (NOT NULL)
   - `subject_type`: `VARCHAR(30)` (e.g., `theory`, `lab`)
   - `description`: `TEXT`

7. **`subject_offerings`**
   - `id`: `INTEGER` (PK, Serial)
   - `semester_id`: `INTEGER` (FK → `semesters.id` ON DELETE CASCADE)
   - `section_group_id`: `INTEGER` (FK → `section_groups.id` ON DELETE CASCADE)
   - `subject_id`: `INTEGER` (FK → `subjects.id` ON DELETE CASCADE)
   - `lecture_hours`: `INTEGER`
   - `tutorial_hours`: `INTEGER`
   - `practical_hours`: `INTEGER`
   - *Constraint:* `UNIQUE (semester_id, section_group_id, subject_id)`

8. **`syllabus_units`**
   - `id`: `INTEGER` (PK, Serial)
   - `subject_id`: `INTEGER` (FK → `subjects.id` ON DELETE CASCADE)
   - `unit_number`: `INTEGER` (NOT NULL)
   - `unit_name`: `VARCHAR(255)` (NOT NULL)
   - `description`: `TEXT`
   - `proposed_lectures`: `INTEGER`
   - *Constraint:* `UNIQUE (subject_id, unit_number)`

9. **`syllabus_topics`**
   - `id`: `INTEGER` (PK, Serial)
   - `unit_id`: `INTEGER` (FK → `syllabus_units.id` ON DELETE CASCADE)
   - `name`: `VARCHAR(255)` (NOT NULL)
   - `description`: `TEXT`
   - `display_order`: `INTEGER` (DEFAULT 1)

10. **`syllabus_subtopics`**
    - `id`: `INTEGER` (PK, Serial)
    - `topic_id`: `INTEGER` (FK → `syllabus_topics.id` ON DELETE CASCADE)
    - `name`: `VARCHAR(255)` (NOT NULL)
    - `display_order`: `INTEGER` (DEFAULT 1)

11. **`course_outcomes`**
    - `id`: `INTEGER` (PK, Serial)
    - `subject_id`: `INTEGER` (FK → `subjects.id` ON DELETE CASCADE)
    - `co_number`: `INTEGER` (NOT NULL)
    - `description`: `TEXT` (NOT NULL)
    - `bloom_levels`: `VARCHAR(50)`
    - *Constraint:* `UNIQUE (subject_id, co_number)`

12. **`textbooks`**
    - `id`: `INTEGER` (PK, Serial)
    - `subject_id`: `INTEGER` (FK → `subjects.id` ON DELETE CASCADE)
    - `title`: `VARCHAR(500)` (NOT NULL)
    - `authors`: `VARCHAR(500)`
    - `publisher`: `VARCHAR(255)`
    - `edition`: `VARCHAR(100)`
    - `book_type`: `VARCHAR(30)`
    - `display_order`: `INTEGER` (DEFAULT 1)

---

### B. User & Assignment Models
13. **`teachers`**
    - `id`: `INTEGER` (PK, Serial)
    - `teacher_code`: `VARCHAR(50)` (UNIQUE, INDEX, NOT NULL)
    - `full_name`: `VARCHAR(150)` (NOT NULL)
    - `email`: `VARCHAR(255)` (UNIQUE, INDEX)
    - `password_hash`: `VARCHAR(255)` (Argon2 hash)
    - `is_active`: `BOOLEAN` (NOT NULL, DEFAULT `true`)
    - `created_at`: `TIMESTAMP WITHOUT TIME ZONE` (DEFAULT `NOW()`)
    - `updated_at`: `TIMESTAMP WITHOUT TIME ZONE`

14. **`students`**
    - `id`: `INTEGER` (PK, Serial)
    - `student_code`: `VARCHAR(50)` (UNIQUE, INDEX, NOT NULL)
    - `full_name`: `VARCHAR(150)` (NOT NULL)
    - `email`: `VARCHAR(255)` (UNIQUE, INDEX)
    - `password_hash`: `VARCHAR(255)` (Argon2 hash)
    - `section_id`: `INTEGER` (FK → `sections.id` ON DELETE RESTRICT)
    - `is_active`: `BOOLEAN` (NOT NULL, DEFAULT `true`)
    - `created_at`: `TIMESTAMP WITHOUT TIME ZONE` (DEFAULT `NOW()`)
    - `updated_at`: `TIMESTAMP WITHOUT TIME ZONE`

15. **`teacher_assignments`**
    - `id`: `INTEGER` (PK, Serial)
    - `teacher_id`: `INTEGER` (FK → `teachers.id` ON DELETE CASCADE)
    - `semester_id`: `INTEGER` (FK → `semesters.id` ON DELETE CASCADE)
    - `section_id`: `INTEGER` (FK → `sections.id` ON DELETE CASCADE)
    - `subject_id`: `INTEGER` (FK → `subjects.id` ON DELETE CASCADE)
    - `assignment_type`: `VARCHAR(50)` (DEFAULT `'primary'`)
    - `created_at`: `TIMESTAMP WITHOUT TIME ZONE` (DEFAULT `NOW()`)
    - *Constraint:* `UNIQUE (teacher_id, semester_id, section_id, subject_id)`

---

### C. Doubt & Resolution Models
16. **`doubts`**
    - `id`: `INTEGER` (PK, Serial)
    - `doubt_code`: `VARCHAR(36)` (UNIQUE, INDEX, NOT NULL)
    - `student_id`: `INTEGER` (FK → `students.id` ON DELETE CASCADE)
    - `section_id`: `INTEGER` (FK → `sections.id` ON DELETE RESTRICT)
    - `subject_id`: `INTEGER` (FK → `subjects.id` ON DELETE RESTRICT)
    - `teacher_id`: `INTEGER` (FK → `teachers.id` ON DELETE SET NULL)
    - `topic_id`: `INTEGER` (FK → `syllabus_topics.id` ON DELETE SET NULL)
    - `subtopic_id`: `INTEGER` (FK → `syllabus_subtopics.id` ON DELETE SET NULL)
    - `title`: `VARCHAR(255)`
    - `description`: `TEXT`
    - `question`: `TEXT` (NOT NULL)
    - `status`: `VARCHAR(30)` (INDEX, NOT NULL, DEFAULT `'pending'`)
    - `is_anonymous_to_teacher`: `BOOLEAN` (NOT NULL, DEFAULT `true`)
    - `created_at`: `TIMESTAMP WITHOUT TIME ZONE` (DEFAULT `NOW()`)
    - `updated_at`: `TIMESTAMP WITHOUT TIME ZONE`

17. **`doubt_subtopics`**
    - `id`: `INTEGER` (PK, Serial)
    - `doubt_id`: `INTEGER` (FK → `doubts.id` ON DELETE CASCADE)
    - `subtopic_id`: `INTEGER` (FK → `syllabus_subtopics.id` ON DELETE CASCADE)
    - *Constraint:* `UNIQUE (doubt_id, subtopic_id)`

18. **`doubt_answers`**
    - `id`: `INTEGER` (PK, Serial)
    - `doubt_id`: `INTEGER` (FK → `doubts.id` ON DELETE CASCADE)
    - `teacher_id`: `INTEGER` (FK → `teachers.id` ON DELETE RESTRICT)
    - `answer_text`: `TEXT` (NOT NULL)
    - `resource_url`: `VARCHAR(1000)`
    - `created_at`: `TIMESTAMP WITHOUT TIME ZONE` (DEFAULT `NOW()`)
    - `updated_at`: `TIMESTAMP WITHOUT TIME ZONE`

19. **`attachments`**
    - `id`: `INTEGER` (PK, Serial)
    - `doubt_id`: `INTEGER` (FK → `doubts.id` ON DELETE CASCADE)
    - `original_filename`: `VARCHAR(255)` (NOT NULL)
    - `stored_filename`: `VARCHAR(255)` (UNIQUE, NOT NULL)
    - `mime_type`: `VARCHAR(100)` (NOT NULL)
    - `file_size`: `INTEGER` (NOT NULL)
    - `storage_path`: `VARCHAR(1000)` (NOT NULL, Supabase Storage key)
    - `uploaded_at`: `TIMESTAMP WITHOUT TIME ZONE` (DEFAULT `NOW()`)

---

### D. Knowledge Library & Doubt Sessions
20. **`library_entries`**
    - `id`: `INTEGER` (PK, Serial)
    - `doubt_id`: `INTEGER` (FK → `doubts.id` ON DELETE CASCADE, UNIQUE)
    - `published_by_teacher_id`: `INTEGER` (FK → `teachers.id` ON DELETE RESTRICT)
    - `published_at`: `TIMESTAMP WITHOUT TIME ZONE` (DEFAULT `NOW()`)

21. **`saved_entries`**
    - `id`: `INTEGER` (PK, Serial)
    - `student_id`: `INTEGER` (FK → `students.id` ON DELETE CASCADE)
    - `library_entry_id`: `INTEGER` (FK → `library_entries.id` ON DELETE CASCADE)
    - `saved_at`: `TIMESTAMP WITHOUT TIME ZONE` (DEFAULT `NOW()`)
    - *Constraint:* `UNIQUE (student_id, library_entry_id)`

22. **`doubt_sessions`**
    - `id`: `INTEGER` (PK, Serial)
    - `teacher_id`: `INTEGER` (FK → `teachers.id` ON DELETE CASCADE)
    - `section_id`: `INTEGER` (FK → `sections.id` ON DELETE RESTRICT)
    - `subject_id`: `INTEGER` (FK → `subjects.id` ON DELETE RESTRICT)
    - `title`: `VARCHAR(255)` (NOT NULL)
    - `description`: `TEXT`
    - `session_date`: `TIMESTAMP WITHOUT TIME ZONE`
    - `starts_at`: `TIMESTAMP WITHOUT TIME ZONE`
    - `ends_at`: `TIMESTAMP WITHOUT TIME ZONE`
    - `submission_opens_at`: `TIMESTAMP WITHOUT TIME ZONE` (NOT NULL)
    - `submission_closes_at`: `TIMESTAMP WITHOUT TIME ZONE` (NOT NULL)
    - `status`: `VARCHAR(30)` (INDEX, NOT NULL, DEFAULT `'upcoming'`)
    - `is_active`: `BOOLEAN` (NOT NULL, DEFAULT `true`)
    - `created_at`: `TIMESTAMP WITHOUT TIME ZONE` (DEFAULT `NOW()`)

23. **`session_topics`**
    - `id`: `INTEGER` (PK, Serial)
    - `session_id`: `INTEGER` (FK → `doubt_sessions.id` ON DELETE CASCADE)
    - `topic_id`: `INTEGER` (FK → `syllabus_topics.id` ON DELETE CASCADE)
    - *Constraint:* `UNIQUE (session_id, topic_id)`

24. **`session_doubts`**
    - `id`: `INTEGER` (PK, Serial)
    - `session_id`: `INTEGER` (FK → `doubt_sessions.id` ON DELETE CASCADE)
    - `student_id`: `INTEGER` (FK → `students.id` ON DELETE CASCADE)
    - `topic_id`: `INTEGER` (FK → `syllabus_topics.id` ON DELETE RESTRICT)
    - `question`: `TEXT` (NOT NULL)
    - `created_at`: `TIMESTAMP WITHOUT TIME ZONE` (DEFAULT `NOW()`)
    - `updated_at`: `TIMESTAMP WITHOUT TIME ZONE`
    - `is_edited`: `BOOLEAN` (NOT NULL, DEFAULT `false`)
