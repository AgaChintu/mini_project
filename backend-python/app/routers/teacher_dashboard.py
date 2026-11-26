from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Request
from fastapi.responses import Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_
from pydantic import BaseModel, Field, ValidationError

from app.database import get_db
from app.security import decode_access_token
from app.models.user import Teacher
from app.models.academic import Subject, Section, Semester
from app.models.assignment import TeacherAssignment, SubjectTeacherAssignment
from app.models.doubt import Doubt, DoubtAnswer, Attachment
from app.services.ai_service import ai_service
from app.services.storage import storage_service

router = APIRouter(
    prefix="/api/teacher",
    tags=["Teacher Dashboard & Doubts"],
)

security = HTTPBearer()


# ==========================================
# AUTHENTICATION DEPENDENCY
# ==========================================

def get_current_teacher(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> Teacher:
    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired login token.",
        )

    if str(payload.get("role", "")).upper() != "TEACHER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Teacher privileges required.",
        )

    teacher_id = int(payload.get("sub") or payload.get("user_id"))
    teacher = db.query(Teacher).filter(
        Teacher.id == teacher_id,
        Teacher.is_active == True,
    ).first()

    if not teacher:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Teacher account not found or deactivated.",
        )

    return teacher


# ==========================================
# REQUEST SCHEMAS
# ==========================================

class TeacherAnswerRequest(BaseModel):
    answer_text: str = Field(..., min_length=5)
    resource_url: Optional[str] = None
    resolve_cluster: bool = Field(False, description="Whether to also resolve identical questions in the same cluster")


class DoubtStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(pending|in_progress|resolved)$")


class TeacherProfileUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=150)
    email: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    profile_info: Optional[str] = None


# ==========================================
# HELPER FUNCTIONS
# ==========================================

def get_teacher_subject_ids(db: Session, teacher_id: int) -> List[int]:
    """Retrieves all distinct subject IDs assigned to a teacher from both assignment models."""
    sta_ids = [
        r[0] for r in db.query(SubjectTeacherAssignment.subject_id)
        .filter(SubjectTeacherAssignment.teacher_id == teacher_id, SubjectTeacherAssignment.is_active == True)
        .all()
    ]
    ta_ids = [
        r[0] for r in db.query(TeacherAssignment.subject_id)
        .filter(TeacherAssignment.teacher_id == teacher_id)
        .all()
    ]
    return sorted(list(set(sta_ids + ta_ids)))


def is_teacher_assigned_to_subject(db: Session, teacher_id: int, subject_id: int) -> bool:
    """Checks if a teacher is assigned to a subject in either model."""
    sta = db.query(SubjectTeacherAssignment).filter(
        SubjectTeacherAssignment.teacher_id == teacher_id,
        SubjectTeacherAssignment.subject_id == subject_id,
        SubjectTeacherAssignment.is_active == True,
    ).first()
    if sta:
        return True
    ta = db.query(TeacherAssignment).filter(
        TeacherAssignment.teacher_id == teacher_id,
        TeacherAssignment.subject_id == subject_id,
    ).first()
    return ta is not None


def filter_doubts_for_teacher(query, teacher_id: int):
    """Teachers primarily see doubts routed to them or unassigned doubts for their subject."""
    return query.filter(or_(Doubt.teacher_id == teacher_id, Doubt.teacher_id == None))


# ==========================================
# 1. TEACHER DASHBOARD OVERVIEW
# ==========================================

@router.get("/dashboard")
def get_teacher_dashboard(
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """
    Returns complete dashboard data for the logged-in teacher:
    - Profile info (name, department, designation)
    - Dynamically assigned subjects
    - Doubt statistics (total received, pending, resolved routed to this teacher)
    - Recent anonymous doubts across assigned subjects
    """
    subject_ids = get_teacher_subject_ids(db, teacher.id)
    assigned_subjects = db.query(Subject).filter(Subject.id.in_(subject_ids)).all() if subject_ids else []

    # Map section codes from TeacherAssignment
    ta_records = db.query(TeacherAssignment).filter(TeacherAssignment.teacher_id == teacher.id).all()
    sec_map = {}
    for a in ta_records:
        if a.subject_id and a.section:
            sec_map.setdefault(a.subject_id, set()).add(a.section.code)

    total_doubts = 0
    resolved_doubts = 0
    pending_doubts = 0

    subjects_data = []
    for subj in assigned_subjects:
        sec_codes = sorted(list(sec_map.get(subj.id, set())))

        subj_doubts = filter_doubts_for_teacher(
            db.query(Doubt).filter(Doubt.subject_id == subj.id),
            teacher.id,
        ).all()
        s_total = len(subj_doubts)
        s_resolved = sum(1 for d in subj_doubts if d.status == "resolved" or len(d.answers) > 0)
        s_pending = s_total - s_resolved

        total_doubts += s_total
        resolved_doubts += s_resolved
        pending_doubts += s_pending

        subjects_data.append({
            "id": subj.id,
            "code": subj.code or f"SUB-{subj.id}",
            "name": subj.name,
            "sections": sec_codes,
            "total_doubts": s_total,
            "pending_doubts": s_pending,
            "resolved_doubts": s_resolved,
        })

    # Recent anonymous doubts routed to this teacher across assigned subjects
    recent_query = db.query(Doubt)
    if subject_ids:
        recent_query = recent_query.filter(Doubt.subject_id.in_(subject_ids))
        recent_query = filter_doubts_for_teacher(recent_query, teacher.id)
    else:
        recent_query = recent_query.filter(Doubt.id == -1)

    recent_doubts = recent_query.order_by(desc(Doubt.created_at)).limit(6).all()

    recent_activity = []
    for d in recent_doubts:
        recent_activity.append({
            "id": d.id,
            "doubt_code": d.doubt_code,
            "title": d.title or d.question[:60],
            "subject_name": d.subject.name if d.subject else "Subject",
            "status": d.status,
            "created_at": d.created_at.isoformat() if d.created_at else None,
            "has_answers": len(d.answers) > 0,
            "ai_summary": d.ai_summary or d.title or d.question[:100],
        })

    return {
        "profile": {
            "teacher_id": teacher.id,
            "college_id": teacher.teacher_code,
            "full_name": teacher.full_name,
            "email": teacher.email,
            "department": teacher.department or "Computer Science & Engineering",
            "designation": teacher.designation or "Assistant Professor",
            "profile_info": teacher.profile_info,
        },
        "statistics": {
            "assigned_subjects_count": len(assigned_subjects),
            "total_doubts": total_doubts,
            "pending_doubts": pending_doubts,
            "resolved_doubts": resolved_doubts,
        },
        "assigned_subjects": subjects_data,
        "recent_activity": recent_activity,
    }


# ==========================================
# 2. MY ASSIGNED SUBJECTS ONLY
# ==========================================

@router.get("/subjects")
def get_teacher_subjects(
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """
    Returns only the subjects assigned to the logged-in teacher from the database.
    Does NOT use hardcoded subject mappings.
    """
    subject_ids = get_teacher_subject_ids(db, teacher.id)
    if not subject_ids:
        return {"success": True, "count": 0, "data": []}

    subjects = db.query(Subject).filter(Subject.id.in_(subject_ids)).all()

    ta_records = db.query(TeacherAssignment).filter(TeacherAssignment.teacher_id == teacher.id).all()
    sec_map = {}
    for a in ta_records:
        if a.subject_id and a.section:
            sec_map.setdefault(a.subject_id, set()).add(a.section.code)

    data = []
    for s in subjects:
        sections = sorted(list(sec_map.get(s.id, set())))

        doubts = filter_doubts_for_teacher(
            db.query(Doubt).filter(Doubt.subject_id == s.id),
            teacher.id,
        ).all()
        total_d = len(doubts)
        resolved_d = sum(1 for d in doubts if d.status == "resolved" or len(d.answers) > 0)

        data.append({
            "id": s.id,
            "code": s.code or f"SUB-{s.id}",
            "name": s.name,
            "subject_type": s.subject_type or "theory",
            "description": s.description or f"Syllabus for {s.name}",
            "sections": sections,
            "total_doubts": total_d,
            "pending_doubts": total_d - resolved_d,
            "resolved_doubts": resolved_d,
        })

    return {"success": True, "count": len(data), "data": data}


# ==========================================
# 3. SUBJECT-WISE ANONYMOUS DOUBT CLUSTERING
# ==========================================

@router.get("/subjects/{subject_id}/doubts")
def get_subject_doubts_for_teacher(
    subject_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """
    Returns doubts for a subject routed to this teacher or unassigned, processed with:
    - AI-generated summaries
    - Extracted keywords/tags
    - Clustered / grouped semantically similar doubts
    - Aggregate student count per cluster
    - STRICT ANONYMIZATION: Student names/IDs are completely omitted
    """
    if not is_teacher_assigned_to_subject(db, teacher.id, subject_id):
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to view doubts for this subject.",
        )

    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found.")

    doubts = (
        filter_doubts_for_teacher(
            db.query(Doubt).filter(Doubt.subject_id == subject_id),
            teacher.id,
        )
        .order_by(desc(Doubt.created_at))
        .all()
    )

    # Use AI service to cluster similar doubts
    clusters = ai_service.cluster_doubts_for_teacher(doubts)

    total_count = len(doubts)
    resolved_count = sum(1 for d in doubts if d.status == "resolved" or len(d.answers) > 0)
    pending_count = total_count - resolved_count

    ai_overview = (
        f"Analysis for {subject.name}: {total_count} doubt{'s' if total_count != 1 else ''} routed to you across {len(clusters)} topic cluster{'s' if len(clusters) != 1 else ''}. "
        f"{pending_count} pending teacher verification."
        if total_count > 0
        else f"No doubts currently pending for you in {subject.name}."
    )

    return {
        "success": True,
        "subject": {
            "id": subject.id,
            "code": subject.code or f"SUB-{subject.id}",
            "name": subject.name,
        },
        "ai_overview": ai_overview,
        "statistics": {
            "total_doubts": total_count,
            "pending_doubts": pending_count,
            "resolved_doubts": resolved_count,
            "cluster_count": len(clusters),
        },
        "clusters": clusters,
    }


# ==========================================
# 4. SINGLE ANONYMOUS DOUBT DETAIL
# ==========================================

@router.get("/doubts/{doubt_id}")
def get_teacher_doubt_detail(
    doubt_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """
    Returns anonymous doubt detail for teacher review.
    Does NOT reveal student name, registration number, email or student ID.
    """
    doubt = db.query(Doubt).filter(Doubt.id == doubt_id).first()
    if not doubt:
        raise HTTPException(status_code=404, detail="Doubt not found.")

    # Check assignment
    if not is_teacher_assigned_to_subject(db, teacher.id, doubt.subject_id):
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to view doubts for this subject.",
        )

    if doubt.teacher_id is not None and doubt.teacher_id != teacher.id:
        raise HTTPException(
            status_code=403,
            detail="This doubt is routed to another faculty member.",
        )

    answers = []
    for ans in doubt.answers:
        answers.append({
            "id": ans.id,
            "answer_text": ans.answer_text,
            "teacher_name": ans.teacher.full_name if ans.teacher else "Teacher",
            "resource_url": ans.resource_url,
            "answer_attachment_name": getattr(ans, "answer_attachment_name", None),
            "answer_attachment_mime": getattr(ans, "answer_attachment_mime", None),
            "created_at": ans.created_at.isoformat() if ans.created_at else None,
        })

    attachments = [
        {
            "id": att.id,
            "original_filename": att.original_filename,
            "mime_type": att.mime_type,
            "file_size": att.file_size,
        }
        for att in getattr(doubt, "attachments", [])
    ]

    return {
        "success": True,
        "doubt": {
            "id": doubt.id,
            "doubt_code": doubt.doubt_code,
            "title": doubt.title or doubt.question[:60],
            "description": doubt.description or doubt.question,
            "question": doubt.question,
            "status": doubt.status,
            "created_at": doubt.created_at.isoformat() if doubt.created_at else None,
            "ai_summary": doubt.ai_summary,
            "keywords": [k.strip() for k in (doubt.keywords or "").split(", ") if k.strip()],
            "cluster_title": doubt.cluster_title,
            "subject": {
                "id": doubt.subject.id if doubt.subject else None,
                "name": doubt.subject.name if doubt.subject else "Subject",
                "code": doubt.subject.code if doubt.subject else "",
            },
            "attachments": attachments,
            "answers": answers,
            "is_anonymous": True,
        },
    }


# ==========================================
# 5. HUMAN-IN-THE-LOOP ANSWER VERIFICATION
# Only human teachers have authority to publish final answers
# ==========================================

ALLOWED_MIME_TYPES = {"image/png", "image/jpeg", "application/pdf"}
MAX_FILE_SIZE = 10 * 1024 * 1024

@router.post("/doubts/{doubt_id}/answer", status_code=status.HTTP_201_CREATED)
async def publish_verified_answer(
    doubt_id: int,
    request: Request,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """
    Teacher publishes a human-verified answer (accepts either JSON or multipart/form-data):
    - Verifies teacher is authorized for the subject
    - Saves verified answer linked to the teacher
    - Updates doubt status to 'resolved'
    - Broadcasts answer to all students who submitted doubts in the same cluster if resolve_cluster is True
    - Optionally stores a solution file attachment (image/PDF)
    """
    content_type = (request.headers.get("content-type") or "").lower()
    solution_file = None

    if "multipart/form-data" in content_type:
        form = await request.form()
        raw_text = str(form.get("answer_text") or "")
        raw_url = form.get("resource_url")
        raw_resolve = str(form.get("resolve_cluster") or "false").lower() in ("true", "1", "yes", "on")
        maybe_file = form.get("solution_file")
        if maybe_file is not None and getattr(maybe_file, "filename", None):
            solution_file = maybe_file
        try:
            data = TeacherAnswerRequest(
                answer_text=raw_text,
                resource_url=str(raw_url) if raw_url else None,
                resolve_cluster=raw_resolve,
            )
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=exc.errors())
    else:
        try:
            body = await request.json()
            data = TeacherAnswerRequest(**body)
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=exc.errors())
        except Exception:
            raise HTTPException(status_code=422, detail="Invalid request payload.")

    answer_text = data.answer_text
    resource_url = data.resource_url
    resolve_cluster = data.resolve_cluster
    doubt = db.query(Doubt).filter(Doubt.id == doubt_id).first()
    if not doubt:
        raise HTTPException(status_code=404, detail="Doubt not found.")

    # Authorization check
    if not is_teacher_assigned_to_subject(db, teacher.id, doubt.subject_id):
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to answer doubts for this subject.",
        )

    if doubt.teacher_id is not None and doubt.teacher_id != teacher.id:
        raise HTTPException(
            status_code=403,
            detail="This doubt is routed to another faculty member.",
        )

    if doubt.teacher_id is None:
        doubt.teacher_id = teacher.id

    # Handle solution file upload
    answer_attachment_path = None
    answer_attachment_name = None
    answer_attachment_mime = None

    if solution_file and solution_file.filename:
        if solution_file.content_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {solution_file.filename}. Only PNG, JPG, PDF are allowed.",
            )
        file_bytes = await solution_file.read()
        if len(file_bytes) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"{solution_file.filename} exceeds the 10 MB limit.")

        try:
            meta = storage_service.upload_file_bytes(
                file_bytes=file_bytes,
                original_filename=solution_file.filename,
                content_type=solution_file.content_type,
                subfolder="teacher_solutions",
            )
            answer_attachment_path = meta["storage_path"]
            answer_attachment_name = meta["original_filename"]
            answer_attachment_mime = meta["mime_type"]
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Could not save solution file: {exc}")

    # Save verified answer
    answer = DoubtAnswer(
        doubt_id=doubt.id,
        teacher_id=teacher.id,
        answer_text=answer_text.strip(),
        resource_url=resource_url.strip() if resource_url else None,
        answer_attachment_path=answer_attachment_path,
        answer_attachment_name=answer_attachment_name,
        answer_attachment_mime=answer_attachment_mime,
    )
    db.add(answer)
    doubt.status = "resolved"

    resolved_count = 1
    # If resolve_cluster is True, also publish to pending doubts in the same cluster
    if resolve_cluster and doubt.cluster_title:
        peer_doubts = (
            db.query(Doubt)
            .filter(
                Doubt.subject_id == doubt.subject_id,
                Doubt.cluster_title == doubt.cluster_title,
                Doubt.id != doubt.id,
                Doubt.status != "resolved",
            )
            .all()
        )
        for peer in peer_doubts:
            peer_answer = DoubtAnswer(
                doubt_id=peer.id,
                teacher_id=teacher.id,
                answer_text=answer_text.strip(),
                resource_url=resource_url.strip() if resource_url else None,
                answer_attachment_path=answer_attachment_path,
                answer_attachment_name=answer_attachment_name,
                answer_attachment_mime=answer_attachment_mime,
            )
            db.add(peer_answer)
            peer.status = "resolved"
            resolved_count += 1

    db.commit()
    db.refresh(answer)

    return {
        "success": True,
        "message": f"Answer published successfully. {resolved_count} doubt{'s' if resolved_count != 1 else ''} marked as resolved.",
        "answer": {
            "id": answer.id,
            "answer_text": answer.answer_text,
            "teacher_name": teacher.full_name,
            "resource_url": answer.resource_url,
            "answer_attachment_name": answer.answer_attachment_name,
            "created_at": answer.created_at.isoformat(),
        },
        "doubt_status": "resolved",
        "resolved_doubts_count": resolved_count,
    }


# ==========================================
# 5b. TEACHER DOWNLOAD STUDENT ATTACHMENT
# ==========================================

@router.get("/doubts/{doubt_id}/attachments/{attachment_id}")
def teacher_download_attachment(
    doubt_id: int,
    attachment_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """Teachers can download attachments from doubts they are authorized for."""
    doubt = db.query(Doubt).filter(Doubt.id == doubt_id).first()
    if not doubt:
        raise HTTPException(status_code=404, detail="Doubt not found.")

    if not is_teacher_assigned_to_subject(db, teacher.id, doubt.subject_id):
        raise HTTPException(status_code=403, detail="You are not authorized for this subject.")

    attachment = (
        db.query(Attachment)
        .filter(Attachment.id == attachment_id, Attachment.doubt_id == doubt_id)
        .first()
    )
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found.")

    try:
        file_bytes = storage_service.download_file_bytes(attachment.storage_path)
    except Exception:
        raise HTTPException(status_code=404, detail="Attachment file is missing or unavailable.")

    return Response(
        content=file_bytes,
        media_type=attachment.mime_type,
        headers={"Content-Disposition": f'attachment; filename="{attachment.original_filename}"'},
    )


# ==========================================
# 5c. TEACHER DOWNLOAD OWN SOLUTION FILE
# ==========================================

@router.get("/answers/{answer_id}/solution")
def teacher_download_solution(
    answer_id: int,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """Students and teachers can download the teacher's solution file."""
    answer = db.query(DoubtAnswer).filter(DoubtAnswer.id == answer_id).first()
    if not answer:
        raise HTTPException(status_code=404, detail="Answer not found.")

    if not answer.answer_attachment_path:
        raise HTTPException(status_code=404, detail="No solution file attached to this answer.")

    try:
        file_bytes = storage_service.download_file_bytes(answer.answer_attachment_path)
    except Exception:
        raise HTTPException(status_code=404, detail="Solution file is missing or unavailable.")

    return Response(
        content=file_bytes,
        media_type=answer.answer_attachment_mime or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{answer.answer_attachment_name}"'},
    )


# ==========================================
# 6. UPDATE DOUBT STATUS
# ==========================================

@router.patch("/doubts/{doubt_id}/status")
def update_doubt_status(
    doubt_id: int,
    data: DoubtStatusUpdate,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """Updates doubt status (pending, in_progress, resolved)."""
    doubt = db.query(Doubt).filter(Doubt.id == doubt_id).first()
    if not doubt:
        raise HTTPException(status_code=404, detail="Doubt not found.")

    if not is_teacher_assigned_to_subject(db, teacher.id, doubt.subject_id):
        raise HTTPException(status_code=403, detail="You are not authorized for this subject.")

    if doubt.teacher_id is not None and doubt.teacher_id != teacher.id:
        raise HTTPException(status_code=403, detail="This doubt is routed to another faculty member.")

    doubt.status = data.status
    db.commit()

    return {
        "success": True,
        "message": f"Doubt status updated to '{data.status}'.",
        "doubt_id": doubt.id,
        "new_status": doubt.status,
    }


# ==========================================
# 7. TEACHER PROFILE UPDATE
# ==========================================

@router.put("/profile")
def update_teacher_profile(
    data: TeacherProfileUpdate,
    teacher: Teacher = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """Updates teacher profile information."""
    if data.full_name:
        teacher.full_name = data.full_name.strip()
    if data.email:
        clean_email = data.email.strip().lower()
        if clean_email != teacher.email:
            existing = db.query(Teacher).filter(Teacher.email == clean_email).first()
            if existing:
                raise HTTPException(status_code=409, detail="Email is already in use.")
            teacher.email = clean_email
    if data.department:
        teacher.department = data.department.strip()
    if data.designation:
        teacher.designation = data.designation.strip()
    if data.profile_info is not None:
        teacher.profile_info = data.profile_info.strip()

    db.commit()
    db.refresh(teacher)

    return {
        "success": True,
        "message": "Teacher profile updated successfully.",
        "profile": {
            "teacher_id": teacher.id,
            "college_id": teacher.teacher_code,
            "full_name": teacher.full_name,
            "email": teacher.email,
            "department": teacher.department,
            "designation": teacher.designation,
            "profile_info": teacher.profile_info,
        },
    }
