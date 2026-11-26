from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc
from pydantic import BaseModel, Field, EmailStr

from app.database import get_db
from app.models.admin import Admin
from app.models.user import Teacher, Student
from app.models.academic import Subject, Section, Semester
from app.models.assignment import SubjectTeacherAssignment, TeacherAssignment
from app.models.doubt import Doubt, DoubtAnswer
from app.security import (
    verify_password,
    hash_password,
    create_access_token,
    decode_access_token,
)

router = APIRouter(
    prefix="/api/admin",
    tags=["Admin Management"],
)

security = HTTPBearer()


# ==========================================
# AUTH DEPENDENCY & SCHEMAS
# ==========================================

def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> Admin:
    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired admin login token.",
        )

    if str(payload.get("role", "")).upper() != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required.",
        )

    admin_id = int(payload.get("sub") or payload.get("user_id"))
    admin = db.query(Admin).filter(Admin.id == admin_id, Admin.is_active == True).first()
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin account not found or deactivated.",
        )
    return admin


class AdminLoginRequest(BaseModel):
    login_id: Optional[str] = None
    identifier: Optional[str] = None
    password: str = Field(..., min_length=4)


class TeacherStatusUpdate(BaseModel):
    is_active: bool


class FacultyAssignRequest(BaseModel):
    teacher_id: int
    is_primary: bool = False


class DoubtReassignRequest(BaseModel):
    teacher_id: int


# ==========================================
# 1. ADMIN AUTHENTICATION
# ==========================================

@router.post("/login")
def admin_login(request: AdminLoginRequest, db: Session = Depends(get_db)):
    """Authenticates administrator and issues JWT token."""
    raw_id = request.login_id or request.identifier
    if not raw_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either login_id or identifier must be provided.",
        )
    login_clean = raw_id.strip()

    admin = db.query(Admin).filter(
        or_(Admin.username == login_clean, Admin.email == login_clean.lower())
    ).first()

    if not admin or not verify_password(request.password, admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Admin credentials.",
        )

    if not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin account is inactive. Contact the system owner.",
        )

    token = create_access_token({
        "sub": str(admin.id),
        "username": admin.username,
        "college_id": admin.username,
        "role": "ADMIN",
    })

    return {
        "success": True,
        "access_token": token,
        "token_type": "bearer",
        "user_id": admin.id,
        "username": admin.username,
        "name": admin.full_name,
        "email": admin.email,
        "role": "ADMIN",
    }


@router.get("/me")
def get_admin_profile(admin: Admin = Depends(get_current_admin)):
    """Returns profile information for authenticated administrator."""
    return {
        "success": True,
        "admin": {
            "id": admin.id,
            "username": admin.username,
            "full_name": admin.full_name,
            "email": admin.email,
            "role": "ADMIN",
            "is_active": admin.is_active,
            "created_at": admin.created_at.isoformat() if admin.created_at else None,
        }
    }


# ==========================================
# 2. ADMIN DASHBOARD OVERVIEW
# ==========================================

@router.get("/dashboard")
def get_admin_dashboard(
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Returns platform-wide metrics and active doubts overview:
    - Total students, teachers, subjects, faculty assignments
    - Total doubts, pending doubts, verified doubts
    - Recent doubt activity across the institution
    """
    total_students = db.query(Student).count()
    total_teachers = db.query(Teacher).count()
    total_subjects = db.query(Subject).count()
    active_assignments = db.query(SubjectTeacherAssignment).filter(
        SubjectTeacherAssignment.is_active == True
    ).count()

    total_doubts = db.query(Doubt).count()
    verified_doubts = db.query(Doubt).filter(Doubt.status == "resolved").count()
    pending_doubts = total_doubts - verified_doubts

    # Recent doubts (with strict student privacy preserved)
    recent_doubts_q = db.query(Doubt).order_by(desc(Doubt.created_at)).limit(10).all()
    recent_doubts = []
    for d in recent_doubts_q:
        recent_doubts.append({
            "id": d.id,
            "doubt_code": d.doubt_code,
            "title": d.title or d.question[:60],
            "subject_name": d.subject.name if d.subject else "Subject",
            "assigned_teacher": d.teacher.full_name if d.teacher else "Unassigned",
            "assigned_teacher_id": d.teacher_id,
            "status": d.status,
            "created_at": d.created_at.isoformat() if d.created_at else None,
            "has_answers": len(d.answers) > 0,
        })

    stats_data = {
        "total_students": total_students,
        "total_teachers": total_teachers,
        "total_subjects": total_subjects,
        "active_faculty_assignments": active_assignments,
        "total_active_faculty_assignments": active_assignments,
        "total_doubts": total_doubts,
        "pending_doubts": pending_doubts,
        "resolved_doubts": verified_doubts,
        "verified_doubts": verified_doubts,
    }

    return {
        "success": True,
        "statistics": stats_data,
        "metrics": stats_data,
        "recent_doubts": recent_doubts,
    }


# ==========================================
# 3. TEACHER MANAGEMENT
# ==========================================

@router.get("/teachers")
def list_teachers(
    department: Optional[str] = None,
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Lists all registered teachers with filtering and assigned subjects."""
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
        # Load assigned subjects from SubjectTeacherAssignment
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
        seen_subject_ids = set()

        for a in sta:
            if a.subject and a.subject.id not in seen_subject_ids:
                seen_subject_ids.add(a.subject.id)
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

        # Fallback check on legacy TeacherAssignment
        legacy_assignments = db.query(TeacherAssignment).filter(TeacherAssignment.teacher_id == t.id).all()
        for la in legacy_assignments:
            if la.subject and la.subject.id not in seen_subject_ids:
                seen_subject_ids.add(la.subject.id)
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


@router.get("/teachers/{teacher_id}")
def get_teacher_details(
    teacher_id: int,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Returns single teacher details with complete subject assignments."""
    t = db.query(Teacher).filter(Teacher.id == teacher_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Teacher not found.")

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


@router.patch("/teachers/{teacher_id}/status")
def update_teacher_status(
    teacher_id: int,
    payload: TeacherStatusUpdate,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Activates or deactivates a teacher account safely without deleting records."""
    t = db.query(Teacher).filter(Teacher.id == teacher_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Teacher not found.")

    t.is_active = payload.is_active
    db.commit()
    db.refresh(t)

    return {
        "success": True,
        "message": f"Teacher account {'activated' if t.is_active else 'deactivated'} successfully.",
        "teacher_id": t.id,
        "is_active": t.is_active,
        "teacher": {
            "id": t.id,
            "teacher_code": t.teacher_code,
            "full_name": t.full_name,
            "is_active": t.is_active,
        },
    }


# ==========================================
# 4. SUBJECT MANAGEMENT & FACULTY ASSIGNMENTS
# ==========================================

@router.get("/subjects")
def list_admin_subjects(
    search: Optional[str] = None,
    semester: Optional[int] = None,
    semester_number: Optional[int] = None,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Lists all subjects with their full faculty teams (primary + additional) and semester filtering."""
    query = db.query(Subject)
    if search:
        s = f"%{search.strip()}%"
        query = query.filter(or_(Subject.name.ilike(s), Subject.code.ilike(s)))
    target_sem = semester_number if semester_number is not None else semester
    if target_sem is not None:
        query = query.filter(Subject.semester_number == target_sem)

    subjects = query.order_by(Subject.name).all()
    data = []
    for s in subjects:
        assignments = (
            db.query(SubjectTeacherAssignment)
            .filter(
                SubjectTeacherAssignment.subject_id == s.id,
                SubjectTeacherAssignment.is_active == True,
            )
            .all()
        )

        teachers_list = []
        primary_teacher = None
        for a in assignments:
            if a.teacher:
                t_info = {
                    "assignment_id": a.id,
                    "teacher_id": a.teacher.id,
                    "full_name": a.teacher.full_name,
                    "name": a.teacher.full_name,
                    "teacher_code": a.teacher.teacher_code,
                    "department": a.teacher.department,
                    "designation": getattr(a.teacher, "designation", "Faculty Member") or "Faculty Member",
                    "is_primary": a.is_primary,
                    "is_active": a.is_active,
                }
                teachers_list.append(t_info)
                if a.is_primary:
                    primary_teacher = t_info

        data.append({
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
            "assigned_teachers": teachers_list,
            "assigned_faculty": teachers_list,  # alias for frontend compat
            "faculty_count": len(teachers_list),
            "is_assigned": len(teachers_list) > 0,
        })

    return {"success": True, "count": len(data), "data": data}


@router.get("/subjects/semester-summary")
def get_semester_summary(
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Returns database-driven semester summary: active subjects, counts per semester, unassigned."""
    subjects = db.query(Subject).filter(Subject.is_active == True).all()
    total_active = len(subjects)
    semester_counts = {}
    unassigned = 0
    for s in subjects:
        sem = s.semester_number
        if sem is not None:
            semester_counts[sem] = semester_counts.get(sem, 0) + 1
        else:
            unassigned += 1

    distinct_semesters = len(semester_counts)
    breakdown = [
        {"semester_number": sem_num, "subject_count": count}
        for sem_num, count in sorted(semester_counts.items(), key=lambda x: x[0])
    ]

    return {
        "success": True,
        "total_active_subjects": total_active,
        "total_semesters": distinct_semesters,
        "semester_counts": semester_counts,
        "breakdown": breakdown,
        "unassigned_subjects": unassigned,
        "unassigned_subjects_count": unassigned,
    }


@router.get("/subjects/{subject_id}/teachers")
def get_subject_assigned_teachers(
    subject_id: int,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Returns all active faculty members assigned to a specific subject."""
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found.")

    assignments = (
        db.query(SubjectTeacherAssignment)
        .filter(
            SubjectTeacherAssignment.subject_id == subject_id,
            SubjectTeacherAssignment.is_active == True,
        )
        .order_by(desc(SubjectTeacherAssignment.is_primary))
        .all()
    )

    data = [
        {
            "assignment_id": a.id,
            "teacher_id": a.teacher.id,
            "full_name": a.teacher.full_name,
            "teacher_code": a.teacher.teacher_code,
            "designation": a.teacher.designation,
            "department": a.teacher.department,
            "is_primary": a.is_primary,
            "is_active": a.teacher.is_active,
            "assigned_at": a.assigned_at.isoformat() if a.assigned_at else None,
        }
        for a in assignments if a.teacher
    ]

    return {
        "success": True,
        "subject_id": subject_id,
        "subject_name": subject.name,
        "count": len(data),
        "data": data,
        "assignments": data,
    }


@router.post("/subjects/{subject_id}/teachers", status_code=status.HTTP_201_CREATED)
def assign_teacher_to_subject(
    subject_id: int,
    payload: FacultyAssignRequest,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Assigns a teacher to a subject:
    - Enforces that the teacher must be active
    - Prevents duplicate assignments
    - If is_primary is True, demotes existing primary faculty for this subject to additional
    - Supports multiple faculty per subject
    """
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found.")

    teacher = db.query(Teacher).filter(Teacher.id == payload.teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found.")
    if not teacher.is_active:
        raise HTTPException(status_code=400, detail="Cannot assign an inactive teacher.")

    # Check existing assignment
    existing = (
        db.query(SubjectTeacherAssignment)
        .filter(
            SubjectTeacherAssignment.subject_id == subject_id,
            SubjectTeacherAssignment.teacher_id == teacher.id,
        )
        .first()
    )

    if existing and existing.is_active:
        raise HTTPException(status_code=409, detail="Teacher is already actively assigned to this subject.")

    # If is_primary requested, demote current primary
    if payload.is_primary:
        db.query(SubjectTeacherAssignment).filter(
            SubjectTeacherAssignment.subject_id == subject_id,
            SubjectTeacherAssignment.is_primary == True,
        ).update({"is_primary": False})

    if existing:
        existing.is_active = True
        existing.is_primary = payload.is_primary
        existing.assigned_by_admin_id = admin.id
        existing.assigned_at = datetime.utcnow()
        assignment = existing
    else:
        assignment = SubjectTeacherAssignment(
            subject_id=subject_id,
            teacher_id=teacher.id,
            is_primary=payload.is_primary,
            is_active=True,
            assigned_by_admin_id=admin.id,
        )
        db.add(assignment)

    db.commit()
    db.refresh(assignment)

    return {
        "success": True,
        "message": f"Teacher {teacher.full_name} successfully assigned to {subject.name}.",
        "assignment": {
            "id": assignment.id,
            "subject_id": subject_id,
            "teacher_id": teacher.id,
            "teacher_name": teacher.full_name,
            "is_primary": assignment.is_primary,
        }
    }


@router.delete("/subjects/{subject_id}/teachers/{teacher_id}")
def remove_teacher_assignment(
    subject_id: int,
    teacher_id: int,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Safely deactivates or removes a faculty assignment.
    Historical doubts and verified answers are NEVER deleted.
    """
    assignment = (
        db.query(SubjectTeacherAssignment)
        .filter(
            SubjectTeacherAssignment.subject_id == subject_id,
            SubjectTeacherAssignment.teacher_id == teacher_id,
        )
        .first()
    )
    if not assignment or not assignment.is_active:
        raise HTTPException(status_code=404, detail="Active assignment not found.")

    assignment.is_active = False
    assignment.is_primary = False
    db.commit()

    return {
        "success": True,
        "message": "Faculty assignment removed successfully. Historical records preserved.",
        "subject_id": subject_id,
        "teacher_id": teacher_id,
    }


@router.patch("/subjects/{subject_id}/teachers/{teacher_id}/primary")
def set_primary_faculty(
    subject_id: int,
    teacher_id: int,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Designates a teacher as the primary faculty member for a subject."""
    target = (
        db.query(SubjectTeacherAssignment)
        .filter(
            SubjectTeacherAssignment.subject_id == subject_id,
            SubjectTeacherAssignment.teacher_id == teacher_id,
            SubjectTeacherAssignment.is_active == True,
        )
        .first()
    )
    if not target:
        raise HTTPException(status_code=404, detail="Active faculty assignment not found for this subject.")

    # Demote all other teachers for this subject
    db.query(SubjectTeacherAssignment).filter(
        SubjectTeacherAssignment.subject_id == subject_id,
    ).update({"is_primary": False})

    target.is_primary = True
    db.commit()
    db.refresh(target)

    return {
        "success": True,
        "message": f"{target.teacher.full_name} is now the primary faculty for {target.subject.name}.",
        "subject_id": subject_id,
        "teacher_id": teacher_id,
        "is_primary": True,
    }


# ==========================================
# 5. DOUBT REASSIGNMENT MANAGEMENT
# ==========================================

@router.patch("/doubts/{doubt_id}/reassign")
def reassign_doubt(
    doubt_id: int,
    payload: DoubtReassignRequest,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """
    Reassigns a doubt to another faculty member assigned to the same subject:
    - Validates target teacher is actively assigned to the subject
    - Preserves doubt content, answers, and audit history
    - Updates doubt.teacher_id
    """
    doubt = db.query(Doubt).filter(Doubt.id == doubt_id).first()
    if not doubt:
        raise HTTPException(status_code=404, detail="Doubt not found.")

    target_teacher = db.query(Teacher).filter(Teacher.id == payload.teacher_id).first()
    if not target_teacher:
        raise HTTPException(status_code=404, detail="Target teacher not found.")
    if not target_teacher.is_active:
        raise HTTPException(status_code=400, detail="Cannot reassign to an inactive teacher.")

    # Validate target teacher is assigned to the doubt's subject
    is_assigned = (
        db.query(SubjectTeacherAssignment)
        .filter(
            SubjectTeacherAssignment.subject_id == doubt.subject_id,
            SubjectTeacherAssignment.teacher_id == target_teacher.id,
            SubjectTeacherAssignment.is_active == True,
        )
        .first()
    )
    if not is_assigned:
        # Fallback check on legacy teacher_assignments
        is_assigned = (
            db.query(TeacherAssignment)
            .filter(
                TeacherAssignment.subject_id == doubt.subject_id,
                TeacherAssignment.teacher_id == target_teacher.id,
            )
            .first()
        )
    if not is_assigned:
        raise HTTPException(
            status_code=400,
            detail=f"{target_teacher.full_name} is not assigned to {doubt.subject.name if doubt.subject else 'this subject'}.",
        )

    previous_teacher_name = doubt.teacher.full_name if doubt.teacher else "Unassigned"
    doubt.teacher_id = target_teacher.id
    db.commit()
    db.refresh(doubt)

    return {
        "success": True,
        "message": f"Doubt reassigned from {previous_teacher_name} to {target_teacher.full_name}.",
        "doubt_id": doubt.id,
        "new_assigned_teacher": {
            "id": target_teacher.id,
            "full_name": target_teacher.full_name,
            "teacher_code": target_teacher.teacher_code,
        },
        "doubt": {
            "id": doubt.id,
            "doubt_code": doubt.doubt_code,
            "title": doubt.title,
            "assigned_teacher": {
                "id": target_teacher.id,
                "name": target_teacher.full_name,
                "code": target_teacher.teacher_code,
            },
        },
    }


# ==========================================
# 7. STUDENT ACADEMIC MANAGEMENT
# ==========================================

class StudentSemesterUpdate(BaseModel):
    current_semester: Optional[int] = Field(None, ge=1, le=12)
    semester_number: Optional[int] = Field(None, ge=1, le=12)


@router.get("/students")
def list_admin_students(
    search: Optional[str] = None,
    department: Optional[str] = None,
    semester: Optional[int] = None,
    current_semester: Optional[int] = None,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Lists all registered students with current semester, department and section information."""
    query = db.query(Student)
    if department:
        query = query.filter(Student.department.ilike(f"%{department.strip()}%"))
    target_sem = current_semester if current_semester is not None else semester
    if target_sem is not None:
        query = query.filter(Student.current_semester == target_sem)
    if search:
        s = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Student.full_name.ilike(s),
                Student.student_code.ilike(s),
                Student.email.ilike(s),
            )
        )

    students = query.order_by(Student.student_code).all()
    data = []
    for st in students:
        sec = st.section
        data.append({
            "id": st.id,
            "student_id": st.id,
            "student_code": st.student_code,
            "college_id": st.student_code,
            "full_name": st.full_name,
            "name": st.full_name,
            "email": st.email,
            "department": st.department or (sec.name if sec else "Computer Science & Engineering"),
            "current_semester": st.current_semester,
            "semester": f"Semester {st.current_semester}" if st.current_semester else "Unassigned",
            "section_id": st.section_id,
            "section_code": sec.code if sec else None,
            "is_active": st.is_active,
            "created_at": st.created_at.isoformat() if st.created_at else None,
        })

    return {
        "success": True,
        "count": len(data),
        "data": data,
        "students": data,
    }


@router.get("/students/{student_id}")
def get_admin_student(
    student_id: int,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Returns single student details including current semester."""
    st = db.query(Student).filter(Student.id == student_id).first()
    if not st:
        raise HTTPException(status_code=404, detail="Student not found.")

    sec = st.section
    return {
        "success": True,
        "student": {
            "id": st.id,
            "student_code": st.student_code,
            "college_id": st.student_code,
            "full_name": st.full_name,
            "email": st.email,
            "department": st.department or (sec.name if sec else "Computer Science & Engineering"),
            "current_semester": st.current_semester,
            "semester": f"Semester {st.current_semester}" if st.current_semester else "Unassigned",
            "section_id": st.section_id,
            "section_code": sec.code if sec else None,
            "is_active": st.is_active,
            "created_at": st.created_at.isoformat() if st.created_at else None,
        }
    }


@router.patch("/students/{student_id}/semester")
def update_student_semester(
    student_id: int,
    payload: StudentSemesterUpdate,
    admin: Admin = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Assigns or updates a student's current semester."""
    st = db.query(Student).filter(Student.id == student_id).first()
    if not st:
        raise HTTPException(status_code=404, detail="Student not found.")

    old_sem = st.current_semester
    new_sem = payload.current_semester if payload.current_semester is not None else payload.semester_number
    if new_sem is None:
        raise HTTPException(status_code=422, detail="Either current_semester or semester_number is required.")
    st.current_semester = new_sem
    db.commit()
    db.refresh(st)

    return {
        "success": True,
        "message": f"Student {st.full_name}'s semester updated from {f'Semester {old_sem}' if old_sem else 'Unassigned'} to Semester {new_sem}.",
        "student_id": st.id,
        "previous_semester": old_sem,
        "current_semester": st.current_semester,
        "semester_number": st.current_semester,
        "student": {
            "id": st.id,
            "student_code": st.student_code,
            "full_name": st.full_name,
            "current_semester": st.current_semester,
        }
    }
