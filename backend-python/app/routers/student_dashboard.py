import uuid
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from fastapi.responses import Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc, asc
from pydantic import BaseModel, Field, ValidationError

from app.database import get_db
from app.security import decode_access_token
from app.models.user import Student, Teacher
from app.models.academic import Subject, Section, Semester, AcademicYear, SubjectOffering
from app.models.assignment import TeacherAssignment, SubjectTeacherAssignment
from app.models.doubt import Doubt, DoubtAnswer, Attachment
from app.models.academic_resource import AcademicResource
from app.services.ai_service import ai_service
from app.services.storage import storage_service

router = APIRouter(
    prefix="/api/student",
    tags=["Student Dashboard & Subjects"],
)

security = HTTPBearer()


# ==========================================
# AUTHENTICATION DEPENDENCY
# ==========================================

def get_current_student(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> Student:
    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired login token.",
        )

    if str(payload.get("role", "")).upper() != "STUDENT":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student privileges required.",
        )

    student_id = int(payload.get("sub") or payload.get("user_id"))
    student = db.query(Student).filter(
        Student.id == student_id,
        Student.is_active == True,
    ).first()

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student account not found or deactivated.",
        )

    return student


# ==========================================
# REQUEST SCHEMAS
# ==========================================

class SubmitDoubtRequest(BaseModel):
    subject_id: int
    title: str = Field(..., min_length=3, max_length=255)
    description: str = Field(..., min_length=5)
    teacher_id: Optional[int] = None
    topic_id: Optional[int] = None
    subtopic_id: Optional[int] = None


class StudentProfileUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=150)
    email: Optional[str] = None
    department: Optional[str] = None


# ==========================================
# HELPER: RESOLVE PRIMARY & ALL TEACHERS
# ==========================================

def get_subject_faculty_info(db: Session, subject_id: int, section_id: Optional[int] = None):
    """Returns primary teacher and list of all assigned teachers for a subject."""
    # First check SubjectTeacherAssignment
    sta = (
        db.query(SubjectTeacherAssignment)
        .filter(
            SubjectTeacherAssignment.subject_id == subject_id,
            SubjectTeacherAssignment.is_active == True,
        )
        .order_by(desc(SubjectTeacherAssignment.is_primary))
        .all()
    )

    teachers_list = []
    primary_teacher = None
    seen_ids = set()

    for a in sta:
        if a.teacher and a.teacher.is_active and a.teacher.id not in seen_ids:
            seen_ids.add(a.teacher.id)
            t_data = {
                "id": a.teacher.id,
                "name": a.teacher.full_name,
                "full_name": a.teacher.full_name,
                "code": a.teacher.teacher_code,
                "teacher_code": a.teacher.teacher_code,
                "designation": getattr(a.teacher, "designation", "Faculty Member") or "Faculty Member",
                "department": getattr(a.teacher, "department", "Engineering") or "Engineering",
                "is_primary": a.is_primary,
            }
            teachers_list.append(t_data)
            if a.is_primary and not primary_teacher:
                primary_teacher = t_data

    # Fallback to TeacherAssignment
    if not teachers_list:
        ta_query = db.query(TeacherAssignment).filter(TeacherAssignment.subject_id == subject_id)
        if section_id:
            sec_ta = ta_query.filter(TeacherAssignment.section_id == section_id).first()
            if sec_ta and sec_ta.teacher:
                ta_query = [sec_ta]
        ta_list = ta_query.all() if not isinstance(ta_query, list) else ta_query
        for la in ta_list:
            if la.teacher and la.teacher.is_active and la.teacher.id not in seen_ids:
                seen_ids.add(la.teacher.id)
                t_data = {
                    "id": la.teacher.id,
                    "name": la.teacher.full_name,
                    "full_name": la.teacher.full_name,
                    "code": la.teacher.teacher_code,
                    "teacher_code": la.teacher.teacher_code,
                    "designation": getattr(la.teacher, "designation", "Faculty Member") or "Faculty Member",
                    "department": getattr(la.teacher, "department", "Engineering") or "Engineering",
                    "is_primary": len(teachers_list) == 0,
                }
                teachers_list.append(t_data)
                if not primary_teacher:
                    primary_teacher = t_data

    if teachers_list and not primary_teacher:
        primary_teacher = teachers_list[0]

    return primary_teacher, teachers_list


# ==========================================
# 1. STUDENT DASHBOARD OVERVIEW
# ==========================================

@router.get("/dashboard")
def get_student_dashboard(
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """
    Returns complete dynamic dashboard data for the logged-in student:
    - Profile info (name, department, semester, section, academic year)
    - Dynamically assigned subjects with faculty details
    - Doubt statistics (total, pending, resolved)
    - Recent activity with teacher-verified response snippets
    """
    section = student.section
    semester = section.semester if section else None
    academic_year = section.academic_year if section else None

    # Fetch subjects offered to student's semester
    effective_semester = student.current_semester
    if effective_semester is None and student.section and student.section.semester:
        effective_semester = student.section.semester.semester_number

    subjects_data = []

    if effective_semester is not None:
        subjects_list = (
            db.query(Subject)
            .filter(
                Subject.semester_number == effective_semester,
                Subject.is_active == True,
            )
            .order_by(Subject.name)
            .all()
        )
        # Fallback to section offerings if semester_number not yet assigned to subjects
        if not subjects_list and semester:
            subjects_list = (
                db.query(Subject)
                .join(SubjectOffering, SubjectOffering.subject_id == Subject.id)
                .filter(SubjectOffering.semester_id == semester.id, Subject.is_active == True)
                .distinct()
                .all()
            )

        for subj in subjects_list:
            primary_t, all_t = get_subject_faculty_info(db, subj.id, section.id if section else None)
            teacher_name = primary_t["name"] if primary_t else "Department Faculty"

            my_subj_doubts = db.query(Doubt).filter(
                Doubt.student_id == student.id,
                Doubt.subject_id == subj.id,
            ).count()

            # Academic resources uploaded by faculty for this subject
            my_subj_resources = db.query(AcademicResource).filter(
                AcademicResource.subject_id == subj.id,
                AcademicResource.status == "active",
            ).count()

            subjects_data.append({
                "id": subj.id,
                "code": subj.code or f"SUB-{subj.id}",
                "name": subj.name,
                "type": subj.subject_type or "theory",
                "semester_number": subj.semester_number,
                "semester": f"Semester {subj.semester_number}" if subj.semester_number else (subj.semester_label or ""),
                "teacher_name": teacher_name,
                "primary_teacher": primary_t,
                "assigned_teachers": all_t,
                "my_doubts_count": my_subj_doubts,
                "resources_count": my_subj_resources,
            })
    else:
        # Student has NO semester assigned: empty list per requirements
        subjects_data = []

    # Recent study materials uploaded across accessible subjects
    recent_resources = []
    enrolled_subj_ids = [s["id"] for s in subjects_data]
    if enrolled_subj_ids:
        res_list = (
            db.query(AcademicResource)
            .filter(
                AcademicResource.subject_id.in_(enrolled_subj_ids),
                AcademicResource.status == "active",
            )
            .order_by(desc(AcademicResource.created_at))
            .limit(8)
            .all()
        )
    else:
        res_list = (
            db.query(AcademicResource)
            .filter(AcademicResource.status == "active")
            .order_by(desc(AcademicResource.created_at))
            .limit(8)
            .all()
        )

    for r in res_list:
        recent_resources.append({
            "id": r.id,
            "title": r.title,
            "description": r.description or "",
            "subject_id": r.subject_id,
            "subject_name": r.subject.name if r.subject else "Subject",
            "subject_code": r.subject.code if r.subject else "",
            "teacher_name": r.teacher.full_name if r.teacher else "Faculty Member",
            "faculty_category": r.faculty_category,
            "resource_type": r.resource_type,
            "original_filename": r.original_filename,
            "file_size": r.file_size,
            "youtube_url": r.youtube_url,
            "youtube_video_id": r.youtube_video_id,
            "is_important": r.is_important,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })

    # Doubt statistics for this student
    total_doubts = db.query(Doubt).filter(Doubt.student_id == student.id).count()
    resolved_doubts = (
        db.query(Doubt)
        .filter(Doubt.student_id == student.id, Doubt.status == "resolved")
        .count()
    )
    pending_doubts = total_doubts - resolved_doubts

    # Recent activity
    recent_doubts = (
        db.query(Doubt)
        .filter(Doubt.student_id == student.id)
        .order_by(desc(Doubt.created_at))
        .limit(5)
        .all()
    )

    recent_activity = []
    for d in recent_doubts:
        latest_ans = None
        if d.answers:
            first_ans = d.answers[-1]
            latest_ans = {
                "teacher_name": first_ans.teacher.full_name if first_ans.teacher else "Teacher",
                "answer_text": first_ans.answer_text[:120] + "..." if len(first_ans.answer_text) > 120 else first_ans.answer_text,
                "answered_at": first_ans.created_at.isoformat() if first_ans.created_at else None,
            }

        recent_activity.append({
            "id": d.id,
            "doubt_code": d.doubt_code,
            "title": d.title or d.question[:60],
            "subject_name": d.subject.name if d.subject else "Subject",
            "status": d.status,
            "created_at": d.created_at.isoformat() if d.created_at else None,
            "verified_answer": latest_ans,
        })

    return {
        "profile": {
            "student_id": student.id,
            "college_id": student.student_code,
            "full_name": student.full_name,
            "email": student.email,
            "department": student.department or (section.name if section else "Computer Science"),
            "section": section.code if section else "A",
            "current_semester": effective_semester,
            "semester": f"Semester {effective_semester}" if effective_semester else (semester.name if semester else "Unassigned"),
            "academic_year": academic_year.name if academic_year else "Second Year",
            "has_assigned_semester": effective_semester is not None,
        },
        "statistics": {
            "total_doubts": total_doubts,
            "pending_doubts": pending_doubts,
            "resolved_doubts": resolved_doubts,
            "total_resources": sum(s.get("resources_count", 0) for s in subjects_data),
        },
        "subjects": subjects_data,
        "has_assigned_semester": effective_semester is not None,
        "semester_message": "Your academic semester has not been assigned yet. Please contact your administrator." if effective_semester is None else None,
        "recent_activity": recent_activity,
        "recent_resources": recent_resources,
    }


# ==========================================
# 2. ENROLLED SUBJECTS & AVAILABLE FACULTY
# ==========================================

@router.get("/subjects")
def get_student_subjects(
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """Returns only subjects assigned to the logged-in student's current semester."""
    effective_semester = student.current_semester
    if effective_semester is None and student.section and student.section.semester:
        effective_semester = student.section.semester.semester_number

    if effective_semester is None:
        return {
            "success": True,
            "count": 0,
            "data": [],
            "has_assigned_semester": False,
            "warning": "Your academic semester has not been assigned yet. Please contact your administrator.",
            "message": "Your academic semester has not been assigned yet. Please contact your administrator.",
        }

    subjects = (
        db.query(Subject)
        .filter(
            Subject.semester_number == effective_semester,
            Subject.is_active == True,
        )
        .order_by(Subject.name)
        .all()
    )

    # Fallback to section offerings if semester_number not yet assigned to subjects
    if not subjects and student.section and student.section.semester:
        subjects = (
            db.query(Subject)
            .join(SubjectOffering, SubjectOffering.subject_id == Subject.id)
            .filter(SubjectOffering.semester_id == student.section.semester.id, Subject.is_active == True)
            .distinct()
            .all()
        )

    result = []
    for s in subjects:
        primary_t, all_t = get_subject_faculty_info(db, s.id, student.section_id)
        teacher_name = primary_t["name"] if primary_t else "Department Faculty"

        my_doubts = db.query(Doubt).filter(
            Doubt.student_id == student.id,
            Doubt.subject_id == s.id,
        ).all()

        total_d = len(my_doubts)
        resolved_d = sum(1 for d in my_doubts if d.status == "resolved")

        result.append({
            "id": s.id,
            "code": s.code or f"SUB-{s.id}",
            "name": s.name,
            "semester_number": s.semester_number,
            "semester": f"Semester {s.semester_number}" if s.semester_number else (s.semester_label or ""),
            "subject_type": s.subject_type or "theory",
            "description": s.description or f"Academic syllabus for {s.name}",
            "assigned_teacher": teacher_name,
            "teacher_name": teacher_name,
            "primary_teacher": primary_t,
            "assigned_teachers": all_t,
            "total_doubts": total_d,
            "resolved_doubts": resolved_d,
            "pending_doubts": total_d - resolved_d,
        })

    return {"success": True, "count": len(result), "data": result}


@router.get("/subjects/{subject_id}/teachers")
def get_subject_faculty_for_student(
    subject_id: int,
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """
    Returns active faculty members assigned to the subject for student selection during doubt submission.
    Primary faculty is listed first.
    """
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found.")

    primary_t, all_t = get_subject_faculty_info(db, subject_id, student.section_id)
    return {
        "success": True,
        "subject_id": subject_id,
        "subject_name": subject.name,
        "count": len(all_t),
        "primary_teacher": primary_t,
        "data": all_t,
    }


# ==========================================
# 3. SUBJECT-SPECIFIC DOUBTS (VIEW DOUBTS)
# ==========================================

@router.get("/subjects/{subject_id}/doubts")
def get_subject_doubts_for_student(
    subject_id: int,
    status_filter: Optional[str] = None,
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """
    Returns only the doubts submitted by this student for a specific subject.
    Never exposes other students' doubts.
    """
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found.")

    query = db.query(Doubt).filter(
        Doubt.student_id == student.id,
        Doubt.subject_id == subject_id,
    )
    if status_filter:
        query = query.filter(Doubt.status == status_filter)

    doubts = query.order_by(desc(Doubt.created_at)).all()

    data = []
    for d in doubts:
        answers = []
        for ans in d.answers:
            answers.append({
                "id": ans.id,
                "answer_text": ans.answer_text,
                "teacher_name": ans.teacher.full_name if ans.teacher else "Verified Teacher",
                "teacher_designation": getattr(ans.teacher, "designation", "Faculty Member") if ans.teacher else "Faculty Member",
                "resource_url": ans.resource_url,
                "answer_attachment_name": getattr(ans, "answer_attachment_name", None),
                "answer_attachment_mime": getattr(ans, "answer_attachment_mime", None),
                "created_at": ans.created_at.isoformat() if ans.created_at else None,
            })

        assigned_faculty = None
        if d.teacher:
            assigned_faculty = {
                "id": d.teacher.id,
                "name": d.teacher.full_name,
                "code": d.teacher.teacher_code,
                "designation": getattr(d.teacher, "designation", "Faculty Member") or "Faculty Member",
                "department": getattr(d.teacher, "department", "Engineering") or "Engineering",
            }

        data.append({
            "id": d.id,
            "doubt_code": d.doubt_code,
            "title": d.title or d.question[:60],
            "description": d.description or d.question,
            "status": d.status,
            "created_at": d.created_at.isoformat() if d.created_at else None,
            "assigned_faculty": assigned_faculty,
            "verified_answers": answers,
            "answers_count": len(answers),
            "is_anonymous": d.is_anonymous_to_teacher,
        })

    return {
        "success": True,
        "subject": {
            "id": subject.id,
            "code": subject.code or f"SUB-{subject.id}",
            "name": subject.name,
        },
        "count": len(data),
        "data": data,
        "doubts": data,  # alias for test compatibility
    }


# ==========================================
# 4. SUBMIT ANONYMOUS DOUBT WITH FACULTY SELECTION (+ OPTIONAL ATTACHMENTS)
# ==========================================

ALLOWED_MIME_TYPES = {"image/png", "image/jpeg", "application/pdf"}
MAX_FILE_SIZE = 10 * 1024 * 1024

@router.post("/doubts", status_code=status.HTTP_201_CREATED)
async def submit_anonymous_doubt(
    request: Request,
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """
    Submits a student doubt anonymously (supports both JSON and multipart/form-data with file attachments):
    - Validates subject existence & student semester eligibility
    - Validates selected faculty assignment
    - Validates and stores optional PNG/JPG/PDF attachments
    - Automatically processes AI summary, keywords and clustering
    - Student identity is NEVER exposed to teachers
    """
    content_type = (request.headers.get("content-type") or "").lower()
    uploaded_files = []

    if "multipart/form-data" in content_type:
        form = await request.form()
        raw_subject_id = form.get("subject_id")
        raw_teacher_id = form.get("teacher_id")
        raw_topic_id = form.get("topic_id")
        raw_subtopic_id = form.get("subtopic_id")
        try:
            data = SubmitDoubtRequest(
                subject_id=int(raw_subject_id),
                title=str(form.get("title") or ""),
                description=str(form.get("description") or ""),
                teacher_id=int(raw_teacher_id) if raw_teacher_id and str(raw_teacher_id).strip() not in ("", "0", "null", "None") else None,
                topic_id=int(raw_topic_id) if raw_topic_id and str(raw_topic_id).strip() else None,
                subtopic_id=int(raw_subtopic_id) if raw_subtopic_id and str(raw_subtopic_id).strip() else None,
            )
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=422, detail=f"Invalid form fields: {exc}")
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=exc.errors())

        for item in form.getlist("files"):
            if getattr(item, "filename", None):
                uploaded_files.append(item)
    else:
        try:
            body = await request.json()
            data = SubmitDoubtRequest(**body)
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=exc.errors())
        except Exception:
            raise HTTPException(status_code=422, detail="Invalid JSON request payload.")

    subject = db.query(Subject).filter(Subject.id == data.subject_id).first()
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Selected subject was not found in database.",
        )

    # Resolve student's effective semester (current_semester or section's semester)
    effective_semester = student.current_semester
    if effective_semester is None and student.section and student.section.semester:
        effective_semester = student.section.semester.semester_number

    # Validate student has an assigned semester
    if not effective_semester:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your academic semester has not been assigned yet. Please contact your administrator.",
        )

    # Validate subject belongs to student's current semester (when subject has a semester assigned)
    if subject.semester_number is not None and subject.semester_number != effective_semester:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"You cannot submit a doubt for a subject outside your current semester (Semester {effective_semester}). This subject belongs to Semester {subject.semester_number}.",
        )

    # Resolve assigned teacher
    assigned_teacher_id = None
    if data.teacher_id:
        # Validate that the selected teacher is actively assigned to this subject
        is_assigned = (
            db.query(SubjectTeacherAssignment)
            .filter(
                SubjectTeacherAssignment.subject_id == subject.id,
                SubjectTeacherAssignment.teacher_id == data.teacher_id,
                SubjectTeacherAssignment.is_active == True,
            )
            .first()
        )
        if not is_assigned:
            # Fallback check on legacy TeacherAssignment
            is_assigned = (
                db.query(TeacherAssignment)
                .filter(
                    TeacherAssignment.subject_id == subject.id,
                    TeacherAssignment.teacher_id == data.teacher_id,
                )
                .first()
            )
        if not is_assigned:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Selected faculty member is not assigned to teach this subject.",
            )
        assigned_teacher_id = data.teacher_id
    else:
        # Pick primary faculty
        primary_t, _ = get_subject_faculty_info(db, subject.id, student.section_id)
        if primary_t:
            assigned_teacher_id = primary_t["id"]

    # Process AI summary and semantic tags
    ai_analysis = ai_service.process_new_doubt(
        title=data.title,
        description=data.description,
        subject_name=subject.name,
    )

    # Validate attachments before saving anything
    validated_files = []
    for f in uploaded_files:
        mime = (getattr(f, "content_type", "") or "").lower()
        if mime not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported attachment type for '{f.filename}'. Only PNG, JPG, and PDF are allowed.",
            )
        contents = await f.read()
        if len(contents) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"'{f.filename}' exceeds the 10 MB size limit.",
            )
        if contents:
            validated_files.append((f.filename, mime, contents))

    doubt_code = f"DBT-{uuid.uuid4().hex[:8].upper()}"

    new_doubt = Doubt(
        doubt_code=doubt_code,
        student_id=student.id,
        section_id=student.section_id,
        subject_id=subject.id,
        teacher_id=assigned_teacher_id,
        topic_id=data.topic_id,
        subtopic_id=data.subtopic_id,
        title=data.title.strip(),
        description=data.description.strip(),
        question=data.description.strip(),
        status="pending",
        is_anonymous_to_teacher=True,
        ai_summary=ai_analysis["ai_summary"],
        keywords=ai_analysis["keywords"],
        cluster_title=ai_analysis["cluster_title"],
    )

    saved_paths = []
    try:
        db.add(new_doubt)
        db.flush()

        for orig_name, mime, contents in validated_files:
            meta = storage_service.upload_file_bytes(
                file_bytes=contents,
                original_filename=orig_name,
                content_type=mime,
                subfolder="doubts",
            )
            saved_paths.append(meta["storage_path"])
            db.add(
                Attachment(
                    doubt_id=new_doubt.id,
                    original_filename=meta["original_filename"],
                    stored_filename=meta["stored_filename"],
                    mime_type=meta["mime_type"],
                    file_size=meta["file_size"],
                    storage_path=meta["storage_path"],
                    uploaded_at=datetime.utcnow(),
                )
            )

        db.commit()
        db.refresh(new_doubt)
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        for path in saved_paths:
            try:
                storage_service.delete_file(path)
            except Exception:
                pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not save doubt attachments: {exc}",
        )

    # Fetch assigned teacher info for confirmation
    assigned_teacher_name = new_doubt.teacher.full_name if new_doubt.teacher else "Department Faculty"

    # Build assigned teacher dict
    assigned_teacher_obj = None
    if new_doubt.teacher:
        assigned_teacher_obj = {
            "id": new_doubt.teacher.id,
            "name": new_doubt.teacher.full_name,
            "code": new_doubt.teacher.teacher_code,
            "designation": getattr(new_doubt.teacher, "designation", "Faculty Member") or "Faculty Member",
            "department": getattr(new_doubt.teacher, "department", "Engineering") or "Engineering",
        }

    return {
        "success": True,
        "message": f"Your doubt has been submitted anonymously to {assigned_teacher_name}. A verified response will be published soon.",
        "doubt": {
            "id": new_doubt.id,
            "doubt_code": new_doubt.doubt_code,
            "title": new_doubt.title,
            "subject_name": subject.name,
            "assigned_teacher": assigned_teacher_obj or assigned_teacher_name,
            "status": new_doubt.status,
            "attachment_count": len(validated_files),
            "created_at": new_doubt.created_at.isoformat(),
            "is_anonymous": True,
        },
    }


# ==========================================
# 5. MY DOUBTS (CENTRALIZED SEARCH, FILTER, SORT)
# ==========================================

@router.get("/doubts")
def get_student_doubts(
    subject_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: Optional[str] = "newest",
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """
    Returns only the doubts submitted by the logged-in student across all subjects.
    Supports title search, subject filtering, status filtering, and sorting.
    """
    query = db.query(Doubt).filter(Doubt.student_id == student.id)

    if subject_id:
        query = query.filter(Doubt.subject_id == subject_id)

    if status_filter and status_filter.lower() != "all":
        clean_status = status_filter.lower()
        if clean_status == "answered" or clean_status == "resolved":
            query = query.filter(Doubt.status == "resolved")
        elif clean_status == "pending":
            query = query.filter(Doubt.status == "pending")
        elif clean_status == "under_review" or clean_status == "in_progress":
            query = query.filter(Doubt.status == "in_progress")
        else:
            query = query.filter(Doubt.status == clean_status)

    if search:
        s = f"%{search.strip()}%"
        query = query.filter(or_(Doubt.title.ilike(s), Doubt.description.ilike(s), Doubt.question.ilike(s)))

    if sort_by == "oldest":
        query = query.order_by(asc(Doubt.created_at))
    else:
        query = query.order_by(desc(Doubt.created_at))

    doubts = query.all()

    data = []
    for d in doubts:
        answers = []
        for ans in d.answers:
            answers.append({
                "id": ans.id,
                "answer_text": ans.answer_text,
                "teacher_name": ans.teacher.full_name if ans.teacher else "Verified Teacher",
                "teacher_designation": getattr(ans.teacher, "designation", "Faculty Member") if ans.teacher else "Faculty Member",
                "resource_url": ans.resource_url,
                "answer_attachment_name": getattr(ans, "answer_attachment_name", None),
                "answer_attachment_mime": getattr(ans, "answer_attachment_mime", None),
                "created_at": ans.created_at.isoformat() if ans.created_at else None,
            })

        assigned_faculty = None
        if d.teacher:
            assigned_faculty = {
                "id": d.teacher.id,
                "name": d.teacher.full_name,
                "code": d.teacher.teacher_code,
                "designation": getattr(d.teacher, "designation", "Faculty Member") or "Faculty Member",
                "department": getattr(d.teacher, "department", "Engineering") or "Engineering",
            }

        attachments = [
            {
                "id": att.id,
                "original_filename": att.original_filename,
                "mime_type": att.mime_type,
                "file_size": att.file_size,
            }
            for att in getattr(d, "attachments", [])
        ]

        data.append({
            "id": d.id,
            "doubt_code": d.doubt_code,
            "title": d.title or d.question[:60],
            "description": d.description or d.question,
            "status": d.status,
            "created_at": d.created_at.isoformat() if d.created_at else None,
            "subject": {
                "id": d.subject.id if d.subject else None,
                "name": d.subject.name if d.subject else "Subject",
                "code": d.subject.code if d.subject else "",
            },
            "assigned_faculty": assigned_faculty,
            "attachments": attachments,
            "verified_answers": answers,
            "answers_count": len(answers),
            "is_anonymous": d.is_anonymous_to_teacher,
        })

    return {"success": True, "count": len(data), "data": data}


@router.get("/doubts/{doubt_id}")
def get_single_doubt(
    doubt_id: int,
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """
    Returns complete doubt detail view for student:
    - Section 1: Doubt info
    - Section 2: Assigned faculty info
    - Section 3: Verified answer or pending review notice
    """
    doubt = db.query(Doubt).filter(
        Doubt.id == doubt_id,
        Doubt.student_id == student.id,
    ).first()

    if not doubt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doubt not found or unauthorized.",
        )

    answers = []
    for ans in doubt.answers:
        answers.append({
            "id": ans.id,
            "answer_text": ans.answer_text,
            "teacher_name": ans.teacher.full_name if ans.teacher else "Verified Teacher",
            "teacher_designation": getattr(ans.teacher, "designation", "Faculty Member") if ans.teacher else "Faculty Member",
            "teacher_department": getattr(ans.teacher, "department", "Engineering") if ans.teacher else "Engineering",
            "resource_url": ans.resource_url,
            "answer_attachment_name": getattr(ans, "answer_attachment_name", None),
            "answer_attachment_mime": getattr(ans, "answer_attachment_mime", None),
            "created_at": ans.created_at.isoformat() if ans.created_at else None,
        })

    assigned_faculty = None
    if doubt.teacher:
        assigned_faculty = {
            "id": doubt.teacher.id,
            "name": doubt.teacher.full_name,
            "code": doubt.teacher.teacher_code,
            "designation": getattr(doubt.teacher, "designation", "Faculty Member") or "Faculty Member",
            "department": getattr(doubt.teacher, "department", "Engineering") or "Engineering",
        }

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
            "status": doubt.status,
            "created_at": doubt.created_at.isoformat() if doubt.created_at else None,
            "ai_summary": doubt.ai_summary,
            "keywords": [k.strip() for k in (doubt.keywords or "").split(", ") if k.strip()],
            "subject": {
                "id": doubt.subject.id if doubt.subject else None,
                "name": doubt.subject.name if doubt.subject else "Subject",
                "code": doubt.subject.code if doubt.subject else "",
            },
            "assigned_faculty": assigned_faculty,
            "assigned_teacher": assigned_faculty,  # alias for test compatibility
            "attachments": attachments,
            "verified_answers": answers,
            "answers_count": len(answers),
            "is_anonymous": doubt.is_anonymous_to_teacher,
        },
        "data": {
            "id": doubt.id,
            "doubt_code": doubt.doubt_code,
            "title": doubt.title or doubt.question[:60],
            "description": doubt.description or doubt.question,
            "status": doubt.status,
            "created_at": doubt.created_at.isoformat() if doubt.created_at else None,
            "ai_summary": doubt.ai_summary,
            "keywords": [k.strip() for k in (doubt.keywords or "").split(", ") if k.strip()],
            "subject": {
                "id": doubt.subject.id if doubt.subject else None,
                "name": doubt.subject.name if doubt.subject else "Subject",
                "code": doubt.subject.code if doubt.subject else "",
            },
            "assigned_faculty": assigned_faculty,
            "assigned_teacher": assigned_faculty,  # alias for test compatibility
            "attachments": attachments,
            "verified_answers": answers,
            "answers_count": len(answers),
            "is_anonymous": doubt.is_anonymous_to_teacher,
        },
    }


@router.get("/doubts/{doubt_id}/answer-file/{answer_id}")
def download_teacher_solution_file(
    doubt_id: int,
    answer_id: int,
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """Allows the student who submitted the doubt to download the teacher's solution attachment."""
    doubt = db.query(Doubt).filter(
        Doubt.id == doubt_id,
        Doubt.student_id == student.id,
    ).first()
    if not doubt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doubt not found or unauthorized.")

    answer = db.query(DoubtAnswer).filter(
        DoubtAnswer.id == answer_id,
        DoubtAnswer.doubt_id == doubt.id,
    ).first()
    if not answer or not answer.answer_attachment_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Solution file not found.")

    try:
        file_bytes = storage_service.download_file_bytes(answer.answer_attachment_path)
    except Exception:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Solution file is missing or unavailable.")

    return Response(
        content=file_bytes,
        media_type=answer.answer_attachment_mime or "application/octet-stream",
        headers={
            "Content-Disposition": f'inline; filename="{answer.answer_attachment_name or "solution"}"'
        },
    )


# ==========================================
# 6. PROFILE UPDATE
# ==========================================

@router.put("/profile")
def update_student_profile(
    data: StudentProfileUpdate,
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """Updates permitted profile fields without changing system identity."""
    if data.full_name:
        student.full_name = data.full_name.strip()
    if data.email:
        clean_email = data.email.strip().lower()
        if clean_email != student.email:
            existing = db.query(Student).filter(Student.email == clean_email).first()
            if existing:
                raise HTTPException(status_code=409, detail="Email is already in use.")
            student.email = clean_email
    if data.department:
        student.department = data.department.strip()

    db.commit()
    db.refresh(student)

    return {
        "success": True,
        "message": "Profile updated successfully.",
        "profile": {
            "student_id": student.id,
            "college_id": student.student_code,
            "full_name": student.full_name,
            "email": student.email,
            "department": student.department,
        },
    }
