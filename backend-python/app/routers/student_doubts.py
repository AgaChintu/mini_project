import os
import uuid
import shutil

from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
    File,
    Form,
)

from fastapi.responses import FileResponse, Response
from app.services.storage import storage_service

from fastapi.security import (
    HTTPBearer,
    HTTPAuthorizationCredentials,
)

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.security import decode_access_token

from app.models.user import Student, Teacher

from app.models.academic import (
    Section,
    Semester,
    SectionGroupMember,
    Subject,
    SubjectOffering,
    SyllabusUnit,
    SyllabusTopic,
    SyllabusSubtopic,
)

from app.models.assignment import TeacherAssignment

from app.models.doubt import (
    Doubt,
    DoubtSubtopic,
    Attachment,
)


router = APIRouter(
    prefix="/api/student/doubts",
    tags=["Student Doubts"],
)

security = HTTPBearer()


# ==================================================
# ATTACHMENT CONFIGURATION
# ==================================================

BASE_DIR = Path(__file__).resolve().parents[2]

UPLOAD_DIR = BASE_DIR / "uploads" / "doubts"

UPLOAD_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

MAX_FILE_SIZE = 10 * 1024 * 1024

ALLOWED_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "application/pdf",
}


# ==================================================
# STUDENT AUTHENTICATION
# ==================================================

def get_current_student(
    credentials: HTTPAuthorizationCredentials,
    db: Session,
):

    payload = decode_access_token(
        credentials.credentials
    )

    if not payload:

        raise HTTPException(
            status_code=401,
            detail="Invalid or expired login session.",
        )

    role = str(
        payload.get("role", "")
    ).upper()

    if role != "STUDENT":

        raise HTTPException(
            status_code=403,
            detail="Student access required.",
        )

    user_id = payload.get("user_id") or payload.get("sub")

    try:

        user_id = int(user_id)

    except (TypeError, ValueError):

        raise HTTPException(
            status_code=401,
            detail="Invalid student token.",
        )

    student = db.query(Student).filter(
        Student.id == user_id,
        Student.is_active == True,
    ).first()

    if not student:

        raise HTTPException(
            status_code=401,
            detail="Student account unavailable.",
        )

    return student


def student_dependency(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):

    return get_current_student(
        credentials,
        db,
    )


# ==================================================
# ACADEMIC CONTEXT
# ==================================================

def get_student_semester(db, student):

    """
    Resolve the semester using the student's section
    and available teacher assignments.

    If assignments exist for multiple semesters,
    use the latest semester number.
    """

    semester = (
        db.query(Semester)
        .join(
            TeacherAssignment,
            TeacherAssignment.semester_id == Semester.id,
        )
        .filter(
            TeacherAssignment.section_id == student.section_id,
        )
        .order_by(
            Semester.semester_number.desc()
        )
        .first()
    )

    if semester:
        return semester

    # Fallback: find the latest semester offering
    # subjects to this student's section.

    semester = (
        db.query(Semester)
        .join(
            SubjectOffering,
            SubjectOffering.semester_id == Semester.id,
        )
        .join(
            SectionGroupMember,
            SectionGroupMember.section_group_id
            == SubjectOffering.section_group_id,
        )
        .filter(
            SectionGroupMember.section_id == student.section_id,
        )
        .order_by(
            Semester.semester_number.desc()
        )
        .first()
    )

    return semester


# ==================================================
# GET STUDENT SUBJECTS
# ==================================================

@router.get("/subjects")
def get_student_subjects(
    student: Student = Depends(student_dependency),
    db: Session = Depends(get_db),
):

    semester = get_student_semester(
        db,
        student,
    )

    if not semester:

        return {
            "subjects": [],
            "message": "No active semester or subject offerings found.",
        }

    subjects = (
        db.query(Subject)
        .join(
            SubjectOffering,
            SubjectOffering.subject_id == Subject.id,
        )
        .join(
            SectionGroupMember,
            SectionGroupMember.section_group_id
            == SubjectOffering.section_group_id,
        )
        .filter(
            SectionGroupMember.section_id == student.section_id,
            SubjectOffering.semester_id == semester.id,
            Subject.subject_type == "theory",
        )
        .order_by(
            Subject.name.asc()
        )
        .all()
    )

    return {
        "subjects": [
            {
                "id": subject.id,
                "code": subject.code,
                "name": subject.name,
            }
            for subject in subjects
        ]
    }


# ==================================================
# GET TEACHERS FOR A SUBJECT
# ==================================================

@router.get("/teachers")
def get_subject_teachers(
    subject_id: int,
    student: Student = Depends(student_dependency),
    db: Session = Depends(get_db),
):

    semester = get_student_semester(
        db,
        student,
    )

    if not semester:

        raise HTTPException(
            status_code=404,
            detail="No active semester found.",
        )

    # Confirm that the subject is actually offered
    # to this student's section.

    offering = (
        db.query(SubjectOffering)
        .join(
            SectionGroupMember,
            SectionGroupMember.section_group_id
            == SubjectOffering.section_group_id,
        )
        .filter(
            SectionGroupMember.section_id == student.section_id,
            SubjectOffering.semester_id == semester.id,
            SubjectOffering.subject_id == subject_id,
        )
        .first()
    )

    if not offering:

        raise HTTPException(
            status_code=404,
            detail="This subject is not available for your section.",
        )

    assignments = (
        db.query(
            TeacherAssignment,
            Teacher,
        )
        .join(
            Teacher,
            Teacher.id == TeacherAssignment.teacher_id,
        )
        .filter(
            TeacherAssignment.section_id == student.section_id,
            TeacherAssignment.semester_id == semester.id,
            TeacherAssignment.subject_id == subject_id,
            Teacher.is_active == True,
        )
        .order_by(
            TeacherAssignment.id.asc()
        )
        .all()
    )

    teachers = []

    for assignment, teacher in assignments:

        teachers.append({
            "id": teacher.id,
            "name": teacher.full_name,
        })

    return {
        "teachers": teachers,
        "default_teacher_id": (
            teachers[0]["id"] if teachers else None
        ),
    }


# ==================================================
# GET SUBTOPICS FOR A SUBJECT
# ==================================================

@router.get("/subtopics")
def get_subject_subtopics(
    subject_id: int,
    student: Student = Depends(student_dependency),
    db: Session = Depends(get_db),
):

    semester = get_student_semester(
        db,
        student,
    )

    if not semester:

        raise HTTPException(
            status_code=404,
            detail="No active semester found.",
        )

    offering = (
        db.query(SubjectOffering)
        .join(
            SectionGroupMember,
            SectionGroupMember.section_group_id
            == SubjectOffering.section_group_id,
        )
        .filter(
            SectionGroupMember.section_id == student.section_id,
            SubjectOffering.semester_id == semester.id,
            SubjectOffering.subject_id == subject_id,
        )
        .first()
    )

    if not offering:

        raise HTTPException(
            status_code=404,
            detail="Subject not available for your section.",
        )

    # Return ONLY subtopics.
    #
    # Unit names and parent topic names are deliberately
    # excluded from the response.

    rows = (
        db.query(
            SyllabusSubtopic.id,
            SyllabusSubtopic.name,
            SyllabusSubtopic.display_order,
        )
        .join(
            SyllabusTopic,
            SyllabusTopic.id == SyllabusSubtopic.topic_id,
        )
        .join(
            SyllabusUnit,
            SyllabusUnit.id == SyllabusTopic.unit_id,
        )
        .filter(
            SyllabusUnit.subject_id == subject_id,
        )
        .order_by(
            SyllabusUnit.unit_number.asc(),
            SyllabusTopic.display_order.asc(),
            SyllabusSubtopic.display_order.asc(),
        )
        .all()
    )

    return {
        "subtopics": [
            {
                "id": row.id,
                "name": row.name,
            }
            for row in rows
        ]
    }


# ==================================================
# SUBMIT DOUBT
# ==================================================

@router.post("/")
async def submit_doubt(
    title: str = Form(...),
    description: str = Form(...),
    subject_id: int = Form(...),
    teacher_id: int = Form(0),
    subtopic_ids: str = Form(""),
    files: List[UploadFile] = File(default=[]),

    student: Student = Depends(student_dependency),
    db: Session = Depends(get_db),
):

    title = title.strip()
    description = description.strip()

    if not title:

        raise HTTPException(
            status_code=400,
            detail="Please provide a doubt title.",
        )

    if not description:

        raise HTTPException(
            status_code=400,
            detail="Please explain your doubt.",
        )

    if len(title) > 120:

        raise HTTPException(
            status_code=400,
            detail="Title cannot exceed 120 characters.",
        )

    if len(description) > 1000:

        raise HTTPException(
            status_code=400,
            detail="Description cannot exceed 1000 characters.",
        )

    # --------------------------------------------------
    # PARSE SELECTED SUBTOPIC IDS
    # --------------------------------------------------

    try:

        selected_subtopic_ids = [
            int(value)
            for value in subtopic_ids.split(",")
            if value.strip()
        ]

    except ValueError:

        raise HTTPException(
            status_code=400,
            detail="Invalid subtopic selection.",
        )

    if not selected_subtopic_ids:

        raise HTTPException(
            status_code=400,
            detail="Please select at least one subtopic.",
        )

    selected_subtopic_ids = list(
        dict.fromkeys(selected_subtopic_ids)
    )

    # --------------------------------------------------
    # VALIDATE SUBJECT & SEMESTER ELIGIBILITY
    # --------------------------------------------------

    effective_semester = student.current_semester
    if effective_semester is None and student.section and student.section.semester:
        effective_semester = student.section.semester.semester_number

    if not effective_semester:
        raise HTTPException(
            status_code=400,
            detail="Your academic semester has not been assigned yet. Please contact your administrator.",
        )

    target_subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if target_subject and target_subject.semester_number is not None and target_subject.semester_number != effective_semester:
        raise HTTPException(
            status_code=400,
            detail=f"You cannot submit a doubt for a subject outside your current semester (Semester {effective_semester}).",
        )

    semester = get_student_semester(
        db,
        student,
    )

    if not semester:

        raise HTTPException(
            status_code=404,
            detail="No active semester found.",
        )

    offering = (
        db.query(SubjectOffering)
        .join(
            SectionGroupMember,
            SectionGroupMember.section_group_id
            == SubjectOffering.section_group_id,
        )
        .filter(
            SectionGroupMember.section_id == student.section_id,
            SubjectOffering.semester_id == semester.id,
            SubjectOffering.subject_id == subject_id,
        )
        .first()
    )

    if not offering:

        raise HTTPException(
            status_code=400,
            detail="Invalid subject selection.",
        )

    # --------------------------------------------------
    # VALIDATE TEACHER ASSIGNMENT
    # --------------------------------------------------

    if teacher_id == 0:
        # Auto-pick the first assigned teacher for this subject
        auto_assignment = db.query(TeacherAssignment).filter(
            TeacherAssignment.section_id == student.section_id,
            TeacherAssignment.semester_id == semester.id,
            TeacherAssignment.subject_id == subject_id,
        ).first()
        if not auto_assignment:
            raise HTTPException(
                status_code=400,
                detail="No faculty is assigned to this subject. Please contact your administrator.",
            )
        teacher_id = auto_assignment.teacher_id

    teacher_assignment = db.query(TeacherAssignment).filter(
        TeacherAssignment.teacher_id == teacher_id,
        TeacherAssignment.section_id == student.section_id,
        TeacherAssignment.semester_id == semester.id,
        TeacherAssignment.subject_id == subject_id,
    ).first()

    if not teacher_assignment:

        raise HTTPException(
            status_code=400,
            detail="Selected teacher is not assigned to this subject and section.",
        )

    teacher = db.query(Teacher).filter(
        Teacher.id == teacher_id,
        Teacher.is_active == True,
    ).first()

    if not teacher:

        raise HTTPException(
            status_code=400,
            detail="Selected teacher is unavailable.",
        )

    # --------------------------------------------------
    # VALIDATE SUBTOPICS
    # --------------------------------------------------

    if not selected_subtopic_ids:
        # Allow submission without subtopics (optional)
        selected_subtopics = []
    else:
        selected_subtopics = (
            db.query(SyllabusSubtopic)
            .join(
                SyllabusTopic,
                SyllabusTopic.id == SyllabusSubtopic.topic_id,
            )
            .join(
                SyllabusUnit,
                SyllabusUnit.id == SyllabusTopic.unit_id,
            )
            .filter(
                SyllabusSubtopic.id.in_(selected_subtopic_ids),
                SyllabusUnit.subject_id == subject_id,
            )
            .all()
        )

        if len(selected_subtopics) != len(selected_subtopic_ids):
            raise HTTPException(
                status_code=400,
                detail="One or more selected subtopics do not belong to this subject.",
            )

    # --------------------------------------------------
    # VALIDATE ATTACHMENTS
    # --------------------------------------------------

    for file in files:

        if not file.filename:
            continue

        if file.content_type not in ALLOWED_MIME_TYPES:

            raise HTTPException(
                status_code=400,
                detail=f"Unsupported attachment type: {file.filename}",
            )

        contents = await file.read()

        if len(contents) > MAX_FILE_SIZE:

            raise HTTPException(
                status_code=400,
                detail=f"{file.filename} exceeds the 10 MB limit.",
            )

        await file.seek(0)

    # --------------------------------------------------
    # CREATE DOUBT
    # --------------------------------------------------

    doubt_code = str(uuid.uuid4())

    first_subtopic = selected_subtopics[0] if selected_subtopics else None

    # The existing database has one question column.
    # Store the title and explanation together.

    complete_question = (
        f"{title}\n\n{description}"
    )

    doubt = Doubt(
        doubt_code=doubt_code,

        student_id=student.id,

        section_id=student.section_id,

        subject_id=subject_id,

        teacher_id=teacher_id,

        topic_id=first_subtopic.topic_id if first_subtopic else None,

        subtopic_id=first_subtopic.id if first_subtopic else None,

        question=complete_question,

        status="pending",

        created_at=datetime.now(),

        updated_at=None,

        is_anonymous_to_teacher=True,
    )

    saved_paths = []

    try:

        db.add(doubt)
        db.flush()

        # --------------------------------------------------
        # SAVE ALL SELECTED SUBTOPICS
        # --------------------------------------------------

        for subtopic in selected_subtopics:

            db.add(
                DoubtSubtopic(
                    doubt_id=doubt.id,
                    subtopic_id=subtopic.id,
                )
            )

        # --------------------------------------------------
        # SAVE ATTACHMENT FILES
        # --------------------------------------------------

        for file in files:

            if not file.filename:
                continue

            contents = await file.read()

            if not contents:
                continue

            meta = storage_service.upload_file_bytes(
                file_bytes=contents,
                original_filename=file.filename,
                content_type=file.content_type,
                subfolder="doubts",
            )

            saved_paths.append(meta["storage_path"])

            attachment = Attachment(
                doubt_id=doubt.id,
                original_filename=meta["original_filename"],
                stored_filename=meta["stored_filename"],
                mime_type=meta["mime_type"],
                file_size=meta["file_size"],
                storage_path=meta["storage_path"],
                uploaded_at=datetime.now(),
            )

            db.add(attachment)

        db.commit()

        db.refresh(doubt)

    except Exception:

        db.rollback()

        for path in saved_paths:
            try:
                storage_service.delete_file(path)
            except Exception:
                pass

        raise HTTPException(
            status_code=500,
            detail="Could not submit your doubt. Please try again.",
        )

    return {
        "message": "Doubt submitted successfully.",

        "doubt": {
            "id": doubt.id,
            "doubt_code": doubt.doubt_code,
            "status": doubt.status,
            "created_at": doubt.created_at.isoformat(),
            "subject_id": doubt.subject_id,
            "teacher_id": doubt.teacher_id,
            "subtopic_ids": selected_subtopic_ids,
            "attachment_count": len(saved_paths),
        },
    }


# ==================================================
# DOWNLOAD ATTACHMENT
# ==================================================

@router.get("/attachments/{attachment_id}")
def download_attachment(
    attachment_id: int,
    student: Student = Depends(student_dependency),
    db: Session = Depends(get_db),
):

    attachment = (
        db.query(Attachment)
        .join(
            Doubt,
            Doubt.id == Attachment.doubt_id,
        )
        .filter(
            Attachment.id == attachment_id,
            Doubt.student_id == student.id,
        )
        .first()
    )

    if not attachment:

        raise HTTPException(
            status_code=404,
            detail="Attachment not found.",
        )

    try:
        file_bytes = storage_service.download_file_bytes(attachment.storage_path)
    except Exception:
        raise HTTPException(
            status_code=404,
            detail="Attachment file is missing or unavailable.",
        )

    return Response(
        content=file_bytes,
        media_type=attachment.mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{attachment.original_filename}"'
        },
    )