"""
Academic Library router — faculty resource upload & management + student resource browsing.
Completely independent of AI Copilot / RAG.
"""
import logging
import re
from datetime import datetime
from typing import Optional, List
from pathlib import Path

from fastapi import (
    APIRouter, Depends, HTTPException, status, UploadFile, File,
    Form, Query, Response,
)
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.security import decode_access_token
from app.models.user import Teacher, Student
from app.models.academic import Subject
from app.models.assignment import SubjectTeacherAssignment, TeacherAssignment
from app.models.academic_resource import AcademicResource
from app.services.storage import storage_service
from app.core.config import settings

logger = logging.getLogger("clariq.library")

router = APIRouter(prefix="/api/library", tags=["Academic Library"])
security = HTTPBearer()

LIBRARY_ALLOWED_TYPES = {
    "application/pdf": ".pdf",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}
LIBRARY_MAX_SIZE = 50 * 1024 * 1024  # 50 MB for documents

YOUTUBE_RE = re.compile(
    r"(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([A-Za-z0-9_\-]{11})"
)


# ─────────────────────────── Auth helpers ──────────────────────────────────

def _get_teacher(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> Teacher:
    payload = decode_access_token(credentials.credentials)
    if not payload or str(payload.get("role", "")).upper() != "TEACHER":
        raise HTTPException(status_code=401, detail="Teacher authentication required.")
    tid = int(payload.get("sub") or payload.get("user_id"))
    t = db.query(Teacher).filter(Teacher.id == tid, Teacher.is_active == True).first()
    if not t:
        raise HTTPException(status_code=404, detail="Teacher not found.")
    return t


def _get_student(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> Student:
    payload = decode_access_token(credentials.credentials)
    if not payload or str(payload.get("role", "")).upper() != "STUDENT":
        raise HTTPException(status_code=401, detail="Student authentication required.")
    sid = int(payload.get("sub") or payload.get("user_id"))
    s = db.query(Student).filter(Student.id == sid, Student.is_active == True).first()
    if not s:
        raise HTTPException(status_code=404, detail="Student not found.")
    return s


def _resolve_youtube_id(url: str) -> Optional[str]:
    m = YOUTUBE_RE.search(url)
    return m.group(1) if m else None


def _teacher_category_for_subject(teacher_id: int, subject_id: int, db: Session) -> str:
    """Returns 'PRIMARY' or 'ADDITIONAL' based on SubjectTeacherAssignment."""
    sta = db.query(SubjectTeacherAssignment).filter(
        SubjectTeacherAssignment.teacher_id == teacher_id,
        SubjectTeacherAssignment.subject_id == subject_id,
        SubjectTeacherAssignment.is_active == True,
    ).first()
    if sta:
        return "PRIMARY" if sta.is_primary else "ADDITIONAL"
    # Fallback: check legacy TeacherAssignment
    legacy = db.query(TeacherAssignment).filter(
        TeacherAssignment.teacher_id == teacher_id,
        TeacherAssignment.subject_id == subject_id,
    ).first()
    if legacy:
        return "PRIMARY" if (legacy.assignment_type or "primary").lower() == "primary" else "ADDITIONAL"
    return "ADDITIONAL"


def _resource_to_dict(r: AcademicResource) -> dict:
    return {
        "id": r.id,
        "title": r.title,
        "description": r.description,
        "subject_id": r.subject_id,
        "subject_name": r.subject.name if r.subject else None,
        "subject_code": r.subject.code if r.subject else None,
        "teacher_id": r.teacher_id,
        "teacher_name": r.teacher.full_name if r.teacher else None,
        "faculty_category": r.faculty_category,
        "resource_type": r.resource_type,
        "original_filename": r.original_filename,
        "file_size": r.file_size,
        "mime_type": r.mime_type,
        "youtube_url": r.youtube_url,
        "youtube_video_id": r.youtube_video_id,
        "youtube_thumbnail": r.youtube_thumbnail,
        "youtube_title": r.youtube_title,
        "is_important": r.is_important,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


# ─────────────────────────── Teacher: get my subjects ──────────────────────

@router.get("/teacher/subjects")
def teacher_my_subjects(
    teacher: Teacher = Depends(_get_teacher),
    db: Session = Depends(get_db),
):
    """Returns subjects the authenticated teacher is assigned to with their role."""
    assignments = db.query(SubjectTeacherAssignment).filter(
        SubjectTeacherAssignment.teacher_id == teacher.id,
        SubjectTeacherAssignment.is_active == True,
    ).all()
    subject_ids = {a.subject_id for a in assignments}

    legacy = db.query(TeacherAssignment).filter(
        TeacherAssignment.teacher_id == teacher.id
    ).all()
    for la in legacy:
        subject_ids.add(la.subject_id)

    subjects = db.query(Subject).filter(Subject.id.in_(subject_ids), Subject.is_active == True).all()
    result = []
    for s in subjects:
        cat = _teacher_category_for_subject(teacher.id, s.id, db)
        result.append({
            "id": s.id,
            "code": s.code,
            "name": s.name,
            "faculty_category": cat,
        })
    return {"success": True, "data": result}


# ─────────────────────────── Teacher: upload resource ──────────────────────

@router.post("/teacher/resources", status_code=201)
async def upload_resource(
    subject_id: int = Form(...),
    title: str = Form(...),
    description: str = Form(""),
    resource_type: str = Form(...),  # pdf/doc/docx/youtube
    youtube_url: str = Form(""),
    youtube_title: str = Form(""),
    is_important: str = Form("false"),
    document: Optional[UploadFile] = File(None),
    teacher: Teacher = Depends(_get_teacher),
    db: Session = Depends(get_db),
):
    resource_type = resource_type.lower().strip()
    if resource_type not in ("pdf", "doc", "docx", "youtube"):
        raise HTTPException(400, "resource_type must be pdf, doc, docx, or youtube.")

    subject = db.query(Subject).filter(Subject.id == subject_id, Subject.is_active == True).first()
    if not subject:
        raise HTTPException(404, "Subject not found.")

    faculty_category = _teacher_category_for_subject(teacher.id, subject_id, db)

    sta = db.query(SubjectTeacherAssignment).filter(
        SubjectTeacherAssignment.teacher_id == teacher.id,
        SubjectTeacherAssignment.subject_id == subject_id,
    ).first()
    legacy = db.query(TeacherAssignment).filter(
        TeacherAssignment.teacher_id == teacher.id,
        TeacherAssignment.subject_id == subject_id,
    ).first()
    if not sta and not legacy:
        raise HTTPException(403, "You are not assigned to this subject.")

    # Important flag is only permitted for Additional Faculty
    is_imp = str(is_important).lower() in ("true", "1", "yes")
    if faculty_category != "ADDITIONAL":
        is_imp = False

    resource = AcademicResource(
        title=title.strip(),
        description=description.strip() or None,
        subject_id=subject_id,
        teacher_id=teacher.id,
        faculty_category=faculty_category,
        resource_type=resource_type,
        is_important=is_imp,
        status="active",
    )

    if resource_type == "youtube":
        if not youtube_url.strip():
            raise HTTPException(400, "youtube_url is required for YouTube resources.")
        vid = _resolve_youtube_id(youtube_url.strip())
        if not vid:
            raise HTTPException(400, "Invalid YouTube URL. Must be a valid YouTube watch or short link.")
        resource.youtube_url = youtube_url.strip()
        resource.youtube_video_id = vid
        resource.youtube_thumbnail = f"https://img.youtube.com/vi/{vid}/hqdefault.jpg"
        resource.youtube_title = youtube_title.strip() or title.strip()

    else:
        # Document upload
        if document is None or not (document.filename or "").strip():
            raise HTTPException(400, f"A file is required for resource type '{resource_type}'.")

        ext = Path(document.filename or "").suffix.lower()
        ext_to_mime = {
            ".pdf": "application/pdf",
            ".doc": "application/msword",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }
        ext_to_type = {
            ".pdf": "pdf",
            ".doc": "doc",
            ".docx": "docx",
        }

        content_type = (document.content_type or "").split(";")[0].strip().lower()
        # Accept valid MIME type OR valid file extension (Windows browsers often send application/octet-stream for .doc/.docx)
        if content_type in LIBRARY_ALLOWED_TYPES:
            resolved_ext = LIBRARY_ALLOWED_TYPES[content_type]
            resolved_mime = content_type
        elif ext in ext_to_mime:
            resolved_ext = ext
            resolved_mime = ext_to_mime[ext]
        else:
            raise HTTPException(
                400,
                f"File type '{document.content_type}' ({ext or 'unknown'}) is not supported. Allowed: PDF, DOC, DOCX."
            )

        # Normalize resource_type to match the actual uploaded file extension
        if resolved_ext in ext_to_type:
            resource.resource_type = ext_to_type[resolved_ext]

        file_bytes = await document.read()
        if len(file_bytes) == 0:
            raise HTTPException(400, "Uploaded file is empty.")
        if len(file_bytes) > LIBRARY_MAX_SIZE:
            raise HTTPException(400, "File exceeds maximum allowed size of 50 MB.")

        import uuid
        stored_name = f"{uuid.uuid4().hex}{resolved_ext}"
        storage_key = f"library/{stored_name}"

        from app.services.storage import get_supabase_client
        client = get_supabase_client()
        uploaded_to_cloud = False
        if client:
            try:
                bucket = settings.SUPABASE_STORAGE_BUCKET
                try:
                    client.storage.get_bucket(bucket)
                except Exception:
                    client.storage.create_bucket(bucket, options={"public": False})
                client.storage.from_(bucket).upload(
                    path=storage_key,
                    file=file_bytes,
                    file_options={"content-type": resolved_mime, "upsert": "false"},
                )
                uploaded_to_cloud = True
            except Exception as exc:
                logger.warning("Supabase upload failed: %s — using local fallback.", exc)

        # Always write local fallback
        local_dir = settings.UPLOAD_DIR / "library"
        local_dir.mkdir(parents=True, exist_ok=True)
        (local_dir / stored_name).write_bytes(file_bytes)
        if not uploaded_to_cloud:
            storage_key = str(local_dir / stored_name)

        resource.storage_path = storage_key
        resource.original_filename = document.filename
        resource.file_size = len(file_bytes)
        resource.mime_type = resolved_mime

    db.add(resource)
    db.commit()
    db.refresh(resource)

    return {"success": True, "data": _resource_to_dict(resource)}


# ─────────────────────────── Teacher: list / manage resources ──────────────

@router.get("/teacher/resources")
def teacher_list_resources(
    subject_id: Optional[int] = Query(None),
    resource_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    teacher: Teacher = Depends(_get_teacher),
    db: Session = Depends(get_db),
):
    q = db.query(AcademicResource).filter(
        AcademicResource.teacher_id == teacher.id,
        AcademicResource.status == "active",
    )
    if subject_id:
        q = q.filter(AcademicResource.subject_id == subject_id)
    if resource_type:
        q = q.filter(AcademicResource.resource_type == resource_type.lower())
    if search:
        like = f"%{search}%"
        q = q.filter(
            AcademicResource.title.ilike(like) | AcademicResource.description.ilike(like)
        )
    total = q.count()
    resources = q.order_by(desc(AcademicResource.created_at)).offset((page - 1) * per_page).limit(per_page).all()
    return {
        "success": True,
        "total": total,
        "page": page,
        "per_page": per_page,
        "data": [_resource_to_dict(r) for r in resources],
    }


class ResourceUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=300)
    description: Optional[str] = None
    is_important: Optional[bool] = None


@router.put("/teacher/resources/{resource_id}")
def update_resource(
    resource_id: int,
    body: ResourceUpdateRequest,
    teacher: Teacher = Depends(_get_teacher),
    db: Session = Depends(get_db),
):
    r = db.query(AcademicResource).filter(
        AcademicResource.id == resource_id,
        AcademicResource.teacher_id == teacher.id,
        AcademicResource.status == "active",
    ).first()
    if not r:
        raise HTTPException(404, "Resource not found or access denied.")
    if body.title is not None:
        r.title = body.title.strip()
    if body.description is not None:
        r.description = body.description.strip() or None
    if body.is_important is not None:
        if r.faculty_category == "ADDITIONAL":
            r.is_important = body.is_important
        else:
            raise HTTPException(403, "Only Additional Faculty can mark resources as Important.")
    r.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(r)
    return {"success": True, "data": _resource_to_dict(r)}


@router.delete("/teacher/resources/{resource_id}", status_code=200)
def delete_resource(
    resource_id: int,
    teacher: Teacher = Depends(_get_teacher),
    db: Session = Depends(get_db),
):
    r = db.query(AcademicResource).filter(
        AcademicResource.id == resource_id,
        AcademicResource.teacher_id == teacher.id,
        AcademicResource.status == "active",
    ).first()
    if not r:
        raise HTTPException(404, "Resource not found or access denied.")
    # Safe soft delete
    r.status = "deleted"
    r.deleted_at = datetime.utcnow()
    db.commit()
    return {"success": True, "message": "Resource deleted."}


# ─────────────────────────── Teacher: download / preview ───────────────────

@router.get("/teacher/resources/{resource_id}/download")
def teacher_download_resource(
    resource_id: int,
    teacher: Teacher = Depends(_get_teacher),
    db: Session = Depends(get_db),
):
    r = db.query(AcademicResource).filter(
        AcademicResource.id == resource_id,
        AcademicResource.status == "active",
    ).first()
    if not r:
        raise HTTPException(404, "Resource not found.")
    fa = db.query(SubjectTeacherAssignment).filter(
        SubjectTeacherAssignment.teacher_id == teacher.id,
        SubjectTeacherAssignment.subject_id == r.subject_id,
    ).first()
    if not fa:
        raise HTTPException(403, "You are not assigned to this subject.")
    if r.resource_type == "youtube":
        raise HTTPException(400, "YouTube resources cannot be downloaded.")

    file_bytes = storage_service.download_file_bytes(r.storage_path)
    return Response(
        content=file_bytes,
        media_type=r.mime_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{r.original_filename or "resource"}"'},
    )


# ─────────────────────────── Student: get subjects ─────────────────────────

def _get_student_subject_ids(student: Student, db) -> set:
    """
    Returns a set of subject IDs accessible to this student.
    Uses three strategies in order:
      1. SectionGroupMember → SubjectOffering (preferred when populated)
      2. semester_number on Subject (same logic as student dashboard)
      3. All active subjects as final fallback so library is never empty
    """
    from app.models.academic import SectionGroupMember, SubjectOffering

    subject_ids: set = set()

    # Strategy 1: via section → section_group → SubjectOffering
    section = student.section
    if section:
        group_ids = [g[0] for g in db.query(SectionGroupMember.section_group_id).filter(
            SectionGroupMember.section_id == section.id
        ).all()]
        if group_ids:
            ids_q = [s[0] for s in db.query(SubjectOffering.subject_id).filter(
                SubjectOffering.section_group_id.in_(group_ids)
            ).all()]
            subject_ids.update(ids_q)

    # Strategy 2: via current_semester → semester_number on Subject
    cur_sem = student.current_semester
    if not cur_sem and section and section.semester:
        cur_sem = section.semester.semester_number
    if cur_sem:
        ids_sem = [s.id for s in db.query(Subject).filter(
            Subject.semester_number == cur_sem,
            Subject.is_active == True,
        ).all()]
        subject_ids.update(ids_sem)

    # Strategy 3: if still empty, return all active subjects so the library is usable
    if not subject_ids:
        subject_ids = {s.id for s in db.query(Subject).filter(Subject.is_active == True).all()}

    return subject_ids


@router.get("/student/subjects")
def student_my_subjects(
    student: Student = Depends(_get_student),
    db: Session = Depends(get_db),
):
    """
    Returns subjects accessible to the student.
    Enrolled / semester-specific subjects appear first, followed by other active curriculum subjects
    so students can access all learning materials in the Academic Library.
    """
    enrolled_ids = _get_student_subject_ids(student, db)
    all_subjects = db.query(Subject).filter(Subject.is_active == True).order_by(Subject.name).all()

    # Enrolled first, then others
    enrolled = [s for s in all_subjects if s.id in enrolled_ids]
    others = [s for s in all_subjects if s.id not in enrolled_ids]
    ordered_subjects = enrolled + others

    return {"success": True, "data": [
        {"id": s.id, "code": s.code, "name": s.name, "is_enrolled": s.id in enrolled_ids}
        for s in ordered_subjects
    ]}


# ─────────────────────────── Student: browse resources ─────────────────────

@router.get("/student/resources")
def student_list_resources(
    subject_id: int = Query(...),
    resource_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    faculty_category: Optional[str] = Query(None),  # PRIMARY/ADDITIONAL
    important_only: bool = Query(False),
    sort: str = Query("newest"),  # newest / alpha
    page: int = Query(1, ge=1),
    per_page: int = Query(30, ge=1, le=100),
    student: Student = Depends(_get_student),
    db: Session = Depends(get_db),
):
    # Verify subject exists and is active
    s = db.query(Subject).filter(Subject.id == subject_id, Subject.is_active == True).first()
    if not s:
        raise HTTPException(404, "Subject not found or inactive.")

    q = db.query(AcademicResource).filter(
        AcademicResource.subject_id == subject_id,
        AcademicResource.status == "active",
    )
    if resource_type:
        q = q.filter(AcademicResource.resource_type == resource_type.lower())
    if faculty_category:
        q = q.filter(AcademicResource.faculty_category == faculty_category.upper())
    if important_only:
        q = q.filter(AcademicResource.is_important == True)
    if search:
        like = f"%{search}%"
        q = q.filter(
            AcademicResource.title.ilike(like) | AcademicResource.description.ilike(like)
        )
    if sort == "alpha":
        q = q.order_by(AcademicResource.title)
    else:
        q = q.order_by(desc(AcademicResource.created_at))

    total = q.count()
    resources = q.offset((page - 1) * per_page).limit(per_page).all()
    return {
        "success": True,
        "total": total,
        "data": [_resource_to_dict(r) for r in resources],
    }


@router.get("/student/resources/{resource_id}/download")
def student_download_resource(
    resource_id: int,
    student: Student = Depends(_get_student),
    db: Session = Depends(get_db),
):
    r = db.query(AcademicResource).filter(
        AcademicResource.id == resource_id,
        AcademicResource.status == "active",
    ).first()
    if not r:
        raise HTTPException(404, "Resource not found.")
    if r.resource_type == "youtube":
        raise HTTPException(400, "YouTube resources are not downloadable. Use the YouTube link.")

    file_bytes = storage_service.download_file_bytes(r.storage_path)
    return Response(
        content=file_bytes,
        media_type=r.mime_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{r.original_filename or "resource"}"'},
    )
