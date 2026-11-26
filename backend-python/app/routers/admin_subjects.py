"""
Part 4 Admin Router — Full Subject CRUD + Faculty Management Endpoints
Extends existing admin.py with new routes for:
  - GET  /api/admin/subjects/{id}  — single subject detail
  - POST /api/admin/subjects       — create new subject
  - PUT  /api/admin/subjects/{id}  — edit subject
  - DELETE /api/admin/subjects/{id} — soft-delete (archive)
  - GET  /api/admin/faculty-overview — faculty-wise teaching info
"""
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc
from pydantic import BaseModel, Field

from app.database import get_db
from app.models.admin import Admin
from app.models.user import Teacher
from app.models.academic import Subject
from app.models.assignment import SubjectTeacherAssignment, TeacherAssignment
from app.routers.admin import get_current_admin

router = APIRouter(prefix="/api/admin", tags=["Admin Subject Management"])


# ==========================================
# SCHEMAS
# ==========================================

class SubjectCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    code: str = Field(..., min_length=1, max_length=30)
    subject_type: Optional[str] = "theory"
    description: Optional[str] = None
    department: Optional[str] = "Computer Science & Engineering"
    semester_number: Optional[int] = Field(None, ge=1, le=12)
    semester_label: Optional[str] = None
    academic_year_label: Optional[str] = None
    primary_teacher_id: Optional[int] = None
    additional_teacher_ids: Optional[List[int]] = []


class SubjectUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=150)
    code: Optional[str] = Field(None, min_length=1, max_length=30)
    subject_type: Optional[str] = None
    description: Optional[str] = None
    department: Optional[str] = None
    semester_number: Optional[int] = Field(None, ge=1, le=12)
    semester_label: Optional[str] = None
    academic_year_label: Optional[str] = None


class SubjectSemesterUpdate(BaseModel):
    semester_number: int = Field(..., ge=1, le=12)


# ==========================================
# HELPER: BUILD SUBJECT RESPONSE DICT
# ==========================================

def _build_subject_dict(s: Subject, db: Session) -> dict:
    assignments = (
        db.query(SubjectTeacherAssignment)
        .filter(
            SubjectTeacherAssignment.subject_id == s.id,
            SubjectTeacherAssignment.is_active == True,
        )
        .order_by(desc(SubjectTeacherAssignment.is_primary))
        .all()
    )

    primary_teacher = None
    all_teachers = []
    for a in assignments:
        if not a.teacher:
            continue
        t_info = {
            "assignment_id": a.id,
            "teacher_id": a.teacher.id,
            "id": a.teacher.id,
            "full_name": a.teacher.full_name,
            "name": a.teacher.full_name,
            "teacher_code": a.teacher.teacher_code,
            "code": a.teacher.teacher_code,
            "department": a.teacher.department,
            "designation": getattr(a.teacher, "designation", "Faculty") or "Faculty",
            "email": a.teacher.email,
            "is_primary": a.is_primary,
            "is_active": a.is_active,
            "assigned_at": a.assigned_at.isoformat() if a.assigned_at else None,
        }
        all_teachers.append(t_info)
        if a.is_primary and primary_teacher is None:
            primary_teacher = t_info

    return {
        "id": s.id,
        "code": s.code or f"SUB-{s.id}",
        "name": s.name,
        "subject_type": s.subject_type or "theory",
        "description": s.description or "",
        "department": getattr(s, "department", None) or "Computer Science & Engineering",
        "semester_number": getattr(s, "semester_number", None),
        "semester": getattr(s, "semester_label", None) or (f"Semester {s.semester_number}" if getattr(s, "semester_number", None) else ""),
        "semester_label": getattr(s, "semester_label", None) or (f"Semester {s.semester_number}" if getattr(s, "semester_number", None) else ""),
        "academic_year_label": getattr(s, "academic_year_label", None) or "",
        "is_active": getattr(s, "is_active", True),
        "primary_teacher": primary_teacher,
        "assigned_teachers": all_teachers,
        "assigned_faculty": all_teachers,  # alias for frontend compat
        "faculty_count": len(all_teachers),
        "is_assigned": len(all_teachers) > 0,
    }


# ==========================================
# GET SINGLE SUBJECT
# ==========================================

@router.get("/subjects/{subject_id}")
def get_admin_subject(
    subject_id: int,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    s = db.query(Subject).filter(Subject.id == subject_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Subject not found.")
    return {"success": True, "subject": _build_subject_dict(s, db)}


# ==========================================
# CREATE NEW SUBJECT
# ==========================================

@router.post("/subjects", status_code=status.HTTP_201_CREATED)
def create_subject(
    payload: SubjectCreateRequest,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Creates a new subject and optionally assigns primary + additional faculty."""
    # Validate unique code
    existing = db.query(Subject).filter(Subject.code == payload.code.strip().upper()).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Subject code '{payload.code}' already exists.")

    sem_num = payload.semester_number
    sem_label = payload.semester_label
    if sem_num and not sem_label:
        sem_label = f"Semester {sem_num}"

    new_subject = Subject(
        code=payload.code.strip().upper(),
        name=payload.name.strip(),
        subject_type=payload.subject_type or "theory",
        description=payload.description,
        department=payload.department or "Computer Science & Engineering",
        semester_number=sem_num,
        semester_label=sem_label,
        academic_year_label=payload.academic_year_label,
        is_active=True,
        created_at=datetime.utcnow(),
    )
    db.add(new_subject)
    db.flush()  # get ID

    # Assign primary faculty
    if payload.primary_teacher_id:
        teacher = db.query(Teacher).filter(Teacher.id == payload.primary_teacher_id, Teacher.is_active == True).first()
        if teacher:
            assignment = SubjectTeacherAssignment(
                subject_id=new_subject.id,
                teacher_id=teacher.id,
                is_primary=True,
                is_active=True,
                assigned_by_admin_id=admin.id,
            )
            db.add(assignment)

    # Assign additional faculty
    for tid in (payload.additional_teacher_ids or []):
        if tid == payload.primary_teacher_id:
            continue  # skip duplicate
        teacher = db.query(Teacher).filter(Teacher.id == tid, Teacher.is_active == True).first()
        if teacher:
            # Check not duplicate
            already = db.query(SubjectTeacherAssignment).filter(
                SubjectTeacherAssignment.subject_id == new_subject.id,
                SubjectTeacherAssignment.teacher_id == tid,
            ).first()
            if not already:
                assignment = SubjectTeacherAssignment(
                    subject_id=new_subject.id,
                    teacher_id=teacher.id,
                    is_primary=False,
                    is_active=True,
                    assigned_by_admin_id=admin.id,
                )
                db.add(assignment)

    db.commit()
    db.refresh(new_subject)

    return {
        "success": True,
        "message": f"Subject '{new_subject.name}' created successfully.",
        "subject": _build_subject_dict(new_subject, db),
    }


# ==========================================
# EDIT SUBJECT
# ==========================================

@router.put("/subjects/{subject_id}")
def update_subject(
    subject_id: int,
    payload: SubjectUpdateRequest,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Updates subject metadata fields. Faculty assignments are managed separately."""
    s = db.query(Subject).filter(Subject.id == subject_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Subject not found.")

    if payload.name is not None:
        s.name = payload.name.strip()
    if payload.code is not None:
        new_code = payload.code.strip().upper()
        # Check uniqueness
        conflict = db.query(Subject).filter(Subject.code == new_code, Subject.id != subject_id).first()
        if conflict:
            raise HTTPException(status_code=409, detail=f"Subject code '{new_code}' is used by another subject.")
        s.code = new_code
    if payload.subject_type is not None:
        s.subject_type = payload.subject_type
    if payload.description is not None:
        s.description = payload.description
    if payload.department is not None:
        s.department = payload.department
    if payload.semester_number is not None:
        s.semester_number = payload.semester_number
        if not payload.semester_label:
            s.semester_label = f"Semester {payload.semester_number}"
    if payload.semester_label is not None:
        s.semester_label = payload.semester_label
    if payload.academic_year_label is not None:
        s.academic_year_label = payload.academic_year_label

    s.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(s)

    return {
        "success": True,
        "message": f"Subject '{s.name}' updated successfully.",
        "subject": _build_subject_dict(s, db),
    }


@router.patch("/subjects/{subject_id}/semester")
def update_subject_semester(
    subject_id: int,
    payload: SubjectSemesterUpdate,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Updates the assigned semester number of an existing subject."""
    s = db.query(Subject).filter(Subject.id == subject_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Subject not found.")

    old_sem = s.semester_number
    s.semester_number = payload.semester_number
    s.semester_label = f"Semester {payload.semester_number}"
    s.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(s)

    return {
        "success": True,
        "message": f"Subject '{s.name}' semester updated from {f'Semester {old_sem}' if old_sem else 'Unassigned'} to Semester {payload.semester_number}.",
        "subject_id": s.id,
        "previous_semester": old_sem,
        "semester_number": s.semester_number,
        "subject": _build_subject_dict(s, db),
    }


# ==========================================
# ARCHIVE SUBJECT (SOFT DELETE)
# ==========================================

@router.delete("/subjects/{subject_id}")
def archive_subject(
    subject_id: int,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Soft-deletes a subject by marking is_active=False.
    Historical doubts and answers are NEVER deleted.
    Faculty assignments are deactivated.
    """
    s = db.query(Subject).filter(Subject.id == subject_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Subject not found.")

    if not getattr(s, "is_active", True):
        raise HTTPException(status_code=400, detail="Subject is already archived.")

    s.is_active = False
    s.updated_at = datetime.utcnow()

    # Deactivate all faculty assignments
    db.query(SubjectTeacherAssignment).filter(
        SubjectTeacherAssignment.subject_id == subject_id,
    ).update({"is_active": False})

    db.commit()

    return {
        "success": True,
        "message": f"Subject '{s.name}' archived. Historical records preserved.",
        "subject_id": subject_id,
    }


# ==========================================
# RESTORE SUBJECT
# ==========================================

@router.patch("/subjects/{subject_id}/restore")
def restore_subject(
    subject_id: int,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    s = db.query(Subject).filter(Subject.id == subject_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Subject not found.")

    s.is_active = True
    s.updated_at = datetime.utcnow()
    db.commit()

    return {"success": True, "message": f"Subject '{s.name}' restored.", "subject_id": subject_id}


# ==========================================
# FACULTY-WISE OVERVIEW
# ==========================================

@router.get("/faculty-overview")
def get_faculty_overview(
    department: Optional[str] = None,
    search: Optional[str] = None,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Returns a faculty-wise view: each teacher with all assigned subjects, roles, and details."""
    query = db.query(Teacher)
    if department:
        query = query.filter(Teacher.department.ilike(f"%{department.strip()}%"))
    if search:
        s = f"%{search.strip()}%"
        query = query.filter(
            or_(Teacher.full_name.ilike(s), Teacher.teacher_code.ilike(s), Teacher.email.ilike(s))
        )

    teachers = query.order_by(Teacher.full_name).all()
    data = []
    for t in teachers:
        assignments = (
            db.query(SubjectTeacherAssignment)
            .filter(
                SubjectTeacherAssignment.teacher_id == t.id,
                SubjectTeacherAssignment.is_active == True,
            )
            .order_by(desc(SubjectTeacherAssignment.is_primary))
            .all()
        )

        primary_subs = []
        additional_subs = []
        seen_ids = set()

        for a in assignments:
            if not a.subject or a.subject.id in seen_ids:
                continue
            seen_ids.add(a.subject.id)
            sub_info = {
                "id": a.subject.id,
                "subject_id": a.subject.id,
                "code": a.subject.code or f"SUB-{a.subject.id}",
                "name": a.subject.name,
                "full_name": a.subject.name,
                "department": getattr(a.subject, "department", None) or "",
                "semester_label": getattr(a.subject, "semester_label", None) or "",
                "is_primary": a.is_primary,
                "assigned_at": a.assigned_at.isoformat() if a.assigned_at else None,
            }
            if a.is_primary:
                primary_subs.append(sub_info)
            else:
                additional_subs.append(sub_info)

        # Fallback check on legacy TeacherAssignment
        legacy_assignments = db.query(TeacherAssignment).filter(TeacherAssignment.teacher_id == t.id).all()
        for la in legacy_assignments:
            if la.subject and la.subject.id not in seen_ids:
                seen_ids.add(la.subject.id)
                is_prim = len(primary_subs) == 0
                sub_info = {
                    "id": la.subject.id,
                    "subject_id": la.subject.id,
                    "code": la.subject.code or f"SUB-{la.subject.id}",
                    "name": la.subject.name,
                    "full_name": la.subject.name,
                    "department": getattr(la.subject, "department", None) or "",
                    "semester_label": getattr(la.subject, "semester_label", None) or "",
                    "is_primary": is_prim,
                    "assigned_at": None,
                }
                if is_prim:
                    primary_subs.append(sub_info)
                else:
                    additional_subs.append(sub_info)

        all_subs = primary_subs + additional_subs
        data.append({
            "id": t.id,
            "teacher_code": t.teacher_code,
            "faculty_id": t.teacher_code,
            "full_name": t.full_name,
            "name": t.full_name,
            "email": t.email,
            "department": t.department or "",
            "designation": getattr(t, "designation", "Faculty") or "Faculty",
            "is_active": t.is_active,
            "primary_subjects": primary_subs,
            "additional_subjects": additional_subs,
            "assigned_subjects": all_subs,
            "all_subjects": all_subs,
            "primary_count": len(primary_subs),
            "additional_count": len(additional_subs),
            "total_assigned": len(all_subs),
            "total_subjects": len(all_subs),
        })

    return {"success": True, "count": len(data), "data": data}


# ==========================================
# MODULE 7: FACULTY MANAGEMENT & ASSIGNMENT ALIASES
# ==========================================

class FacultyAssignBody(BaseModel):
    teacher_id: Optional[int] = None
    faculty_id: Optional[int] = None
    is_primary: bool = False


class SetPrimaryBody(BaseModel):
    teacher_id: Optional[int] = None
    faculty_id: Optional[int] = None


@router.get("/faculty")
def list_admin_faculty(
    department: Optional[str] = None,
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """GET /api/admin/faculty - Lists all faculty members with assigned subjects."""
    query = db.query(Teacher)
    if department:
        query = query.filter(Teacher.department.ilike(f"%{department.strip()}%"))
    if search:
        s = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Teacher.full_name.ilike(s),
                Teacher.teacher_code.ilike(s),
                Teacher.email.ilike(s),
            )
        )
    if is_active is not None:
        query = query.filter(Teacher.is_active == is_active)

    teachers = query.order_by(Teacher.full_name).all()
    data = []
    for t in teachers:
        sta = (
            db.query(SubjectTeacherAssignment)
            .filter(
                SubjectTeacherAssignment.teacher_id == t.id,
                SubjectTeacherAssignment.is_active == True,
            )
            .order_by(desc(SubjectTeacherAssignment.is_primary))
            .all()
        )
        assigned_subs = []
        primary_subs = []
        additional_subs = []
        seen_ids = set()

        for a in sta:
            if a.subject and a.subject.id not in seen_ids:
                seen_ids.add(a.subject.id)
                sub_dict = {
                    "id": a.subject.id,
                    "subject_id": a.subject.id,
                    "code": a.subject.code or f"SUB-{a.subject.id}",
                    "name": a.subject.name,
                    "full_name": a.subject.name,
                    "is_primary": a.is_primary,
                }
                assigned_subs.append(sub_dict)
                if a.is_primary:
                    primary_subs.append(sub_dict)
                else:
                    additional_subs.append(sub_dict)

        # Fallback to TeacherAssignment
        legacy = db.query(TeacherAssignment).filter(TeacherAssignment.teacher_id == t.id).all()
        for la in legacy:
            if la.subject and la.subject.id not in seen_ids:
                seen_ids.add(la.subject.id)
                is_prim = len(primary_subs) == 0
                sub_dict = {
                    "id": la.subject.id,
                    "subject_id": la.subject.id,
                    "code": la.subject.code or f"SUB-{la.subject.id}",
                    "name": la.subject.name,
                    "full_name": la.subject.name,
                    "is_primary": is_prim,
                }
                assigned_subs.append(sub_dict)
                if is_prim:
                    primary_subs.append(sub_dict)
                else:
                    additional_subs.append(sub_dict)

        data.append({
            "id": t.id,
            "teacher_code": t.teacher_code,
            "faculty_id": t.teacher_code,
            "full_name": t.full_name,
            "name": t.full_name,
            "email": t.email,
            "department": t.department,
            "designation": t.designation,
            "is_active": t.is_active,
            "assigned_subjects": assigned_subs,
            "primary_subjects": primary_subs,
            "additional_subjects": additional_subs,
            "assigned_count": len(assigned_subs),
            "total_subjects": len(assigned_subs),
        })

    return {"success": True, "count": len(data), "data": data, "faculty": data}


@router.get("/faculty/{faculty_id}")
def get_admin_faculty_member(
    faculty_id: int,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """GET /api/admin/faculty/{faculty_id} - Details of single faculty member."""
    t = db.query(Teacher).filter(Teacher.id == faculty_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Faculty member not found.")

    sta = (
        db.query(SubjectTeacherAssignment)
        .filter(
            SubjectTeacherAssignment.teacher_id == t.id,
            SubjectTeacherAssignment.is_active == True,
        )
        .all()
    )
    assigned_subs = [
        {
            "subject_id": a.subject.id,
            "code": a.subject.code,
            "name": a.subject.name,
            "is_primary": a.is_primary,
            "assigned_at": a.assigned_at.isoformat() if a.assigned_at else None,
        }
        for a in sta if a.subject
    ]

    return {
        "success": True,
        "faculty": {
            "id": t.id,
            "teacher_code": t.teacher_code,
            "faculty_id": t.teacher_code,
            "full_name": t.full_name,
            "email": t.email,
            "department": t.department,
            "designation": t.designation,
            "profile_info": t.profile_info,
            "is_active": t.is_active,
            "assigned_subjects": assigned_subs,
        },
        "teacher": {
            "id": t.id,
            "teacher_code": t.teacher_code,
            "full_name": t.full_name,
            "email": t.email,
            "department": t.department,
            "designation": t.designation,
            "profile_info": t.profile_info,
            "is_active": t.is_active,
            "assigned_subjects": assigned_subs,
        }
    }


@router.get("/faculty/{faculty_id}/subjects")
def get_faculty_assigned_subjects(
    faculty_id: int,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """GET /api/admin/faculty/{faculty_id}/subjects - Lists all subjects assigned to a faculty member."""
    t = db.query(Teacher).filter(Teacher.id == faculty_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Faculty member not found.")

    sta = (
        db.query(SubjectTeacherAssignment)
        .filter(
            SubjectTeacherAssignment.teacher_id == t.id,
            SubjectTeacherAssignment.is_active == True,
        )
        .all()
    )

    primary_subs = []
    addl_subs = []
    all_subs = []
    for a in sta:
        if a.subject:
            sub_dict = {
                "id": a.subject.id,
                "code": a.subject.code,
                "name": a.subject.name,
                "department": getattr(a.subject, "department", ""),
                "semester_label": getattr(a.subject, "semester_label", ""),
                "is_primary": a.is_primary,
                "assigned_at": a.assigned_at.isoformat() if a.assigned_at else None,
            }
            all_subs.append(sub_dict)
            if a.is_primary:
                primary_subs.append(sub_dict)
            else:
                addl_subs.append(sub_dict)

    return {
        "success": True,
        "faculty_id": t.id,
        "faculty_name": t.full_name,
        "count": len(all_subs),
        "data": all_subs,
        "subjects": all_subs,
        "primary_subjects": primary_subs,
        "additional_subjects": addl_subs,
    }


@router.get("/subjects/{subject_id}/faculty")
def get_subject_faculty_list(
    subject_id: int,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """GET /api/admin/subjects/{subject_id}/faculty - Returns all assigned faculty."""
    from app.routers.admin import get_subject_assigned_teachers
    return get_subject_assigned_teachers(subject_id, admin, db)


@router.post("/subjects/{subject_id}/faculty", status_code=status.HTTP_201_CREATED)
def assign_faculty_to_subject_alias(
    subject_id: int,
    payload: FacultyAssignBody,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """POST /api/admin/subjects/{subject_id}/faculty - Assigns faculty to subject."""
    from app.routers.admin import assign_teacher_to_subject, FacultyAssignRequest
    tid = payload.teacher_id or payload.faculty_id
    if not tid:
        raise HTTPException(status_code=400, detail="Either teacher_id or faculty_id must be provided.")
    return assign_teacher_to_subject(subject_id, FacultyAssignRequest(teacher_id=tid, is_primary=payload.is_primary), admin, db)


@router.patch("/subjects/{subject_id}/faculty/primary")
def set_primary_faculty_body(
    subject_id: int,
    payload: SetPrimaryBody,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """PATCH /api/admin/subjects/{subject_id}/faculty/primary - Sets primary faculty via JSON body."""
    from app.routers.admin import set_primary_faculty
    tid = payload.teacher_id or payload.faculty_id
    if not tid:
        raise HTTPException(status_code=400, detail="Either teacher_id or faculty_id must be provided.")
    return set_primary_faculty(subject_id, tid, admin, db)


@router.patch("/subjects/{subject_id}/faculty/{teacher_id}/primary")
def set_primary_faculty_path_alias(
    subject_id: int,
    teacher_id: int,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """PATCH /api/admin/subjects/{subject_id}/faculty/{teacher_id}/primary - Path alias."""
    from app.routers.admin import set_primary_faculty
    return set_primary_faculty(subject_id, teacher_id, admin, db)


@router.delete("/subjects/{subject_id}/faculty/{teacher_id}")
def remove_faculty_assignment_alias(
    subject_id: int,
    teacher_id: int,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """DELETE /api/admin/subjects/{subject_id}/faculty/{teacher_id} - Removes faculty assignment."""
    from app.routers.admin import remove_teacher_assignment
    return remove_teacher_assignment(subject_id, teacher_id, admin, db)


# ==========================================
# ADMIN DOUBTS LIST (FOR DOUBT ROUTING TAB)
# ==========================================

@router.get("/doubts")
def list_admin_doubts(
    status_filter: Optional[str] = None,
    subject_id: Optional[int] = None,
    search: Optional[str] = None,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Lists doubts visible to admin for routing/reassignment purposes."""
    from app.models.doubt import Doubt
    from sqlalchemy import or_ as _or, desc as _desc

    query = db.query(Doubt)
    if status_filter and status_filter.lower() != "all":
        query = query.filter(Doubt.status == status_filter.lower())
    if subject_id:
        query = query.filter(Doubt.subject_id == subject_id)
    if search:
        s = f"%{search.strip()}%"
        query = query.filter(_or(Doubt.title.ilike(s), Doubt.question.ilike(s)))

    doubts = query.order_by(_desc(Doubt.created_at)).limit(100).all()
    data = []
    for d in doubts:
        data.append({
            "id": d.id,
            "doubt_code": d.doubt_code,
            "title": d.title or (d.question[:60] if d.question else ""),
            "description": d.description or d.question or "",
            "status": d.status,
            "created_at": d.created_at.isoformat() if d.created_at else None,
            "subject": {
                "id": d.subject.id if d.subject else None,
                "code": d.subject.code if d.subject else "",
                "name": d.subject.name if d.subject else "Subject",
            },
            "assigned_teacher": {
                "id": d.teacher.id if d.teacher else None,
                "name": d.teacher.full_name if d.teacher else "Unassigned",
                "code": d.teacher.teacher_code if d.teacher else "",
            },
        })

    return {"success": True, "count": len(data), "data": data}


