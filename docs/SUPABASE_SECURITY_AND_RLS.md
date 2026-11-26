# ClariQ — Supabase Security, RLS & Identity Protection

**Security Model:** Defense-in-Depth (FastAPI RBAC + PostgreSQL RLS + Supabase Storage Policies)

---

## 1. Core Anonymous Identity Protection

Identity protection is a fundamental requirement of ClariQ:
- In `doubts`, `is_anonymous_to_teacher = true` by default.
- FastAPI controllers never serialize student identity (`full_name`, `email`, `student_code`) in teacher-facing doubt payloads or doubt inbox listings.
- Storage paths use random UUID filenames (`doubts/<uuid>.<ext>`) to ensure original filenames or usernames are not exposed in object URLs or file paths.

---

## 2. Multi-Layer Authorization Structure

### Layer 1: FastAPI Application Layer (Primary Enforcement)
- **Authentication:** Custom JWT signed via `JWT_SECRET_KEY` using HMAC-SHA256 (`HS256`).
- **Student Ownership:** Students can only read or submit doubts and session queries associated with their `student_id`.
- **Teacher Assignment:** Teachers can only access doubts and sessions corresponding to subjects and sections mapped in `teacher_assignments`.

### Layer 2: PostgreSQL Row Level Security (RLS)
RLS is enabled across all sensitive tables to safeguard against direct PostgREST API exposure:

```sql
-- Enable RLS
ALTER TABLE doubts ENABLE ROW LEVEL SECURITY;
ALTER TABLE doubt_answers ENABLE ROW LEVEL SECURITY;
ALTER TABLE attachments ENABLE ROW LEVEL SECURITY;
ALTER TABLE library_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE saved_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE doubt_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE session_doubts ENABLE ROW LEVEL SECURITY;

-- Students can read their own doubts
CREATE POLICY student_own_doubts ON doubts
  FOR SELECT USING (auth.uid()::text = student_id::text);

-- Teachers can read assigned doubts
CREATE POLICY teacher_assigned_doubts ON doubts
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM teacher_assignments ta
      WHERE ta.teacher_id::text = auth.uid()::text
        AND ta.subject_id = doubts.subject_id
        AND ta.section_id = doubts.section_id
    )
  );
```

### Layer 3: Storage Bucket Policies
The `clariq-attachments` bucket restricts access:
- Public read access is **denied**.
- Uploads and signed URL generation require the backend `SUPABASE_SECRET_KEY` (service role).
