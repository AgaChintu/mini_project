# ClariQ — Supabase Storage Architecture & Integration Guide

**Bucket Name:** `clariq-attachments`  
**Bucket Visibility:** **Private** (No direct anonymous public reads)  
**File Types Permitted:** PNG, JPG, JPEG, PDF  
**Maximum Size:** 10 MB per file  

---

## 1. Storage Architecture

All student doubt attachments are stored in Supabase Storage with metadata indexed in the PostgreSQL `attachments` table.

```
Supabase Storage ('clariq-attachments')
  └── doubts/
        ├── a98b4cd65e...pdf
        ├── 7bf12e98fa...png
        └── 3cf209da1b...jpg
```

---

## 2. Security & Access Policy

1. **Private Bucket:** Direct access via public URL `https://.../storage/v1/object/public/clariq-attachments/...` is disabled.
2. **Authorized Downloads:**
   - **Method A (API Stream):** Clients request `GET /api/student/doubts/{code}/attachments/{id}` with Bearer JWT. The backend verifies that the requesting student owns the doubt or the teacher is assigned to the course, then streams bytes directly.
   - **Method B (Signed URL):** The backend issues a 60-second cryptographically signed temporary URL via `storage_service.get_signed_url(...)`.

---

## 3. Storage Service Implementation

The `SupabaseStorageService` (`app/services/storage.py`) enforces:
- Extension & MIME validation before payload upload.
- Content size check (≤ 10 MB).
- Automatic bucket initialization on startup.
- Safe rollback deletion if database commit fails.
