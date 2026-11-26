from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import or_
from pydantic import BaseModel, Field

from app.database import get_db
from app.security import decode_access_token
from app.models.user import Teacher
from app.models.academic import Subject, Section, Semester
from app.models.assignment import TeacherAssignment

router = APIRouter(
    prefix="/api/subjects",
    tags=["Subject Management"],
)

security = HTTPBearer()


# ==========================================
# REQUEST SCHEMAS
# ==========================================

class SubjectCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    code: str = Field(..., min_length=2, max_length=30)
    subject_type: Optional[str] = "theory"
    description: Optional[str] = None


class SubjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=150)
    code: Optional[str] = Field(None, min_length=2, max_length=30)
    subject_type: Optional[str] = None
    description: Optional[str] = None


class TeacherAssignRequest(BaseModel):
    teacher_id: int
    section_id: Optional[int] = None
    semester_id: Optional[int] = None
    assignment_type: Optional[str] = "primary"


# ==========================================
# 1. LIST ALL SUBJECTS
# ==========================================

@router.get("")
def list_all_subjects(db: Session = Depends(get_db)):
    """
    Returns all subjects dynamically from the database,
    including assigned teachers and sections.
    """
    subjects = db.query(Subject).all()
    data = []
    for s in subjects:
        assignments = (
            db.query(TeacherAssignment)
            .filter(TeacherAssignment.subject_id == s.id)
            .all()
        )

        teachers_list = []
        for a in assignments:
            if a.teacher:
                teachers_list.append({
                    "assignment_id": a.id,
                    "teacher_id": a.teacher.id,
                    "teacher_name": a.teacher.full_name,
                    "teacher_code": a.teacher.teacher_code,
                    "section_code": a.section.code if a.section else "All",
                    "semester_name": a.semester.name if a.semester else "",
                })

        data.append({
            "id": s.id,
            "code": s.code or f"SUB-{s.id}",
            "name": s.name,
            "subject_type": s.subject_type or "theory",
            "description": s.description or "",
            "assigned_teachers": teachers_list,
        })

    return {"success": True, "count": len(data), "data": data}


# ==========================================
# 2. GET SUBJECT DETAIL
# ==========================================

@router.get("/{subject_id}")
def get_subject_detail(subject_id: int, db: Session = Depends(get_db)):
    """Returns single subject details."""
    s = db.query(Subject).filter(Subject.id == subject_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Subject not found.")

    assignments = (
        db.query(TeacherAssignment)
        .filter(TeacherAssignment.subject_id == s.id)
        .all()
    )

    teachers_list = [
        {
            "assignment_id": a.id,
            "teacher_id": a.teacher.id,
            "teacher_name": a.teacher.full_name,
            "section_code": a.section.code if a.section else "",
        }
        for a in assignments
        if a.teacher
    ]

    return {
        "success": True,
        "subject": {
            "id": s.id,
            "code": s.code or f"SUB-{s.id}",
            "name": s.name,
            "subject_type": s.subject_type or "theory",
            "description": s.description or "",
            "assigned_teachers": teachers_list,
        },
    }


# ==========================================
# 3. CREATE SUBJECT
# ==========================================

@router.post("", status_code=status.HTTP_201_CREATED)
def create_subject(data: SubjectCreate, db: Session = Depends(get_db)):
    """Creates a new academic subject."""
    clean_code = data.code.strip().upper()
    existing = db.query(Subject).filter(Subject.code == clean_code).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Subject with code '{clean_code}' already exists.",
        )

    subj = Subject(
        code=clean_code,
        name=data.name.strip(),
        subject_type=data.subject_type.strip() if data.subject_type else "theory",
        description=data.description.strip() if data.description else None,
    )
    db.add(subj)
    db.commit()
    db.refresh(subj)

    return {
        "success": True,
        "message": f"Subject '{subj.name}' created successfully.",
        "subject": {
            "id": subj.id,
            "code": subj.code,
            "name": subj.name,
            "subject_type": subj.subject_type,
        },
    }


# ==========================================
# 4. UPDATE SUBJECT
# ==========================================

@router.put("/{subject_id}")
def update_subject(
    subject_id: int,
    data: SubjectUpdate,
    db: Session = Depends(get_db),
):
    """Updates subject metadata without altering doubts or student assignments."""
    subj = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subj:
        raise HTTPException(status_code=404, detail="Subject not found.")

    if data.name:
        subj.name = data.name.strip()
    if data.code:
        clean_code = data.code.strip().upper()
        if clean_code != subj.code:
            existing = db.query(Subject).filter(Subject.code == clean_code).first()
            if existing:
                raise HTTPException(status_code=409, detail=f"Code '{clean_code}' is in use.")
            subj.code = clean_code
    if data.subject_type:
        subj.subject_type = data.subject_type.strip()
    if data.description is not None:
        subj.description = data.description.strip()

    db.commit()
    db.refresh(subj)

    return {
        "success": True,
        "message": f"Subject '{subj.name}' updated successfully.",
        "subject": {
            "id": subj.id,
            "code": subj.code,
            "name": subj.name,
            "subject_type": subj.subject_type,
        },
    }


# ==========================================
# 5. ASSIGN TEACHER TO SUBJECT
# ==========================================

@router.post("/{subject_id}/assign-teacher", status_code=status.HTTP_201_CREATED)
def assign_teacher_to_subject(
    subject_id: int,
    data: TeacherAssignRequest,
    db: Session = Depends(get_db),
):
    """
    Assigns a teacher to a subject and section.
    Prevents duplicate assignments.
    """
    subj = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subj:
        raise HTTPException(status_code=404, detail="Subject not found.")

    teacher = db.query(Teacher).filter(Teacher.id == data.teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found.")

    # Fallback section and semester if not provided
    section_id = data.section_id
    if not section_id:
        first_sec = db.query(Section).first()
        section_id = first_sec.id if first_sec else 1

    semester_id = data.semester_id
    if not semester_id:
        first_sem = db.query(Semester).first()
        semester_id = first_sem.id if first_sem else 1

    # Check duplicate
    existing = (
        db.query(TeacherAssignment)
        .filter(
            TeacherAssignment.teacher_id == teacher.id,
            TeacherAssignment.subject_id == subj.id,
            TeacherAssignment.section_id == section_id,
            TeacherAssignment.semester_id == semester_id,
        )
        .first()
    )
    if existing:
        return {
            "success": True,
            "message": "Assignment already exists.",
            "assignment_id": existing.id,
        }

    assignment = TeacherAssignment(
        teacher_id=teacher.id,
        subject_id=subj.id,
        section_id=section_id,
        semester_id=semester_id,
        assignment_type=data.assignment_type or "primary",
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)

    return {
        "success": True,
        "message": f"Assigned {teacher.full_name} to {subj.name}.",
        "assignment_id": assignment.id,
    }


# ==========================================
# 6. REMOVE TEACHER ASSIGNMENT
# Does NOT delete the subject or existing doubts
# ==========================================

@router.delete("/{subject_id}/assignments/{assignment_id}")
def remove_teacher_assignment(
    subject_id: int,
    assignment_id: int,
    db: Session = Depends(get_db),
):
    """
    Removes a teacher-subject assignment.
    Existing doubts and subject data remain completely intact.
    """
    assignment = (
        db.query(TeacherAssignment)
        .filter(
            TeacherAssignment.id == assignment_id,
            TeacherAssignment.subject_id == subject_id,
        )
        .first()
    )
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found.")

    db.delete(assignment)
    db.commit()

    return {
        "success": True,
        "message": "Teacher assignment removed successfully. Subject and doubts were not affected.",
    }
