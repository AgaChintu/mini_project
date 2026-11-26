import random
import string
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.core.config import settings
from app.models.user import Student, Teacher
from app.models.academic import Section, Semester, AcademicYear, Subject, SubjectOffering
from app.models.assignment import TeacherAssignment
from app.auth_schemas import (
    LoginRequest,
    LoginResponse,
    StudentRegisterRequest,
    TeacherRegisterRequest,
    RegisterResponse,
)
from app.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
)

router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"],
)

security = HTTPBearer(auto_error=False)


def generate_unique_student_code(db: Session, year: int) -> str:
    """Generates an automatic unique student identifier (e.g., STU-2026-4821)."""
    while True:
        suffix = "".join(random.choices(string.digits, k=4))
        code = f"STU-{year}-{suffix}"
        exists = db.query(Student).filter(Student.student_code == code).first()
        if not exists:
            return code


def generate_unique_teacher_code(db: Session) -> str:
    """Generates an automatic unique teacher identifier (e.g., TCH-5921)."""
    while True:
        suffix = "".join(random.choices(string.digits, k=4))
        code = f"TCH-{suffix}"
        exists = db.query(Teacher).filter(Teacher.teacher_code == code).first()
        if not exists:
            return code


# ==========================================
# STUDENT REGISTRATION
# ==========================================

@router.post("/student/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register_student(
    request: StudentRegisterRequest,
    db: Session = Depends(get_db),
):
    """
    Registers a new student account:
    - Validates email uniqueness
    - Hashes password securely with Argon2
    - Automatically generates unique Student ID
    - Dynamically maps to semester and section
    - Assigns relevant subjects
    - Returns JWT token
    """
    if request.password != request.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match.",
        )

    clean_email = request.email.strip().lower()

    # Check if email is already registered across student or teacher
    if db.query(Student).filter(Student.email == clean_email).first() or \
       db.query(Teacher).filter(Teacher.email == clean_email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address is already registered.",
        )

    # Locate or resolve Academic Year & Semester
    sem_num = request.semester_number
    target_year_num = request.academic_year_number or ((sem_num + 1) // 2)

    academic_year = db.query(AcademicYear).filter(
        AcademicYear.year_number == target_year_num
    ).first()
    if not academic_year:
        academic_year = AcademicYear(
            name=f"Year {target_year_num}",
            year_number=target_year_num,
            is_active=True,
        )
        db.add(academic_year)
        db.flush()

    semester = db.query(Semester).filter(
        Semester.academic_year_id == academic_year.id,
        Semester.semester_number == sem_num,
    ).first()
    if not semester:
        semester = Semester(
            academic_year_id=academic_year.id,
            semester_number=sem_num,
            name=f"Semester {sem_num}",
        )
        db.add(semester)
        db.flush()

    # Resolve Section
    clean_sec = request.section_code.strip()
    section = db.query(Section).filter(
        Section.academic_year_id == academic_year.id,
        or_(Section.code == clean_sec, Section.name == clean_sec),
    ).first()

    if not section:
        section = Section(
            academic_year_id=academic_year.id,
            semester_id=semester.id,
            code=clean_sec,
            name=f"Section {clean_sec}",
        )
        db.add(section)
        db.flush()

    # Generate unique student code and hash password
    student_code = generate_unique_student_code(db, datetime.utcnow().year)
    pw_hash = hash_password(request.password)

    new_student = Student(
        student_code=student_code,
        full_name=request.full_name.strip(),
        email=clean_email,
        password_hash=pw_hash,
        section_id=section.id,
        current_semester=request.semester_number,
        department=request.department.strip(),
        is_active=True,
    )
    db.add(new_student)
    db.commit()
    db.refresh(new_student)

    # Count offered subjects for this semester
    offered_count = db.query(SubjectOffering).filter(
        SubjectOffering.semester_id == semester.id
    ).count()

    token = create_access_token({
        "sub": str(new_student.id),
        "college_id": new_student.student_code,
        "role": "STUDENT",
    })

    return {
        "success": True,
        "message": "Student registered successfully.",
        "access_token": token,
        "token_type": "bearer",
        "user_id": new_student.id,
        "college_id": new_student.student_code,
        "name": new_student.full_name,
        "email": new_student.email,
        "role": "STUDENT",
        "department": new_student.department,
        "assigned_subjects_count": offered_count,
    }


# ==========================================
# TEACHER REGISTRATION
# ==========================================

@router.post("/teacher/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register_teacher(
    request: TeacherRegisterRequest,
    db: Session = Depends(get_db),
):
    """
    Registers a new teacher account:
    - Validates official email uniqueness
    - Hashes password securely with Argon2
    - Automatically generates unique Teacher ID
    - Assigns initial subjects if specified
    - Returns JWT token
    """
    if request.password != request.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match.",
        )

    # Verify institutional faculty authorization key
    if request.faculty_invite_code.strip() != settings.FACULTY_REGISTRATION_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid faculty authorization key. Teacher registration requires an authorized institutional key.",
        )

    clean_email = request.email.strip().lower()

    if db.query(Teacher).filter(Teacher.email == clean_email).first() or \
       db.query(Student).filter(Student.email == clean_email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address is already registered.",
        )

    teacher_code = generate_unique_teacher_code(db)
    pw_hash = hash_password(request.password)

    new_teacher = Teacher(
        teacher_code=teacher_code,
        full_name=request.full_name.strip(),
        email=clean_email,
        password_hash=pw_hash,
        department=request.department.strip(),
        designation=request.designation.strip(),
        profile_info=request.profile_info.strip() if request.profile_info else None,
        is_active=True,
    )
    db.add(new_teacher)
    db.flush()

    assigned_count = 0
    if request.subject_ids:
        # Default section and semester for initial assignment
        first_section = db.query(Section).first()
        first_semester = db.query(Semester).first()
        if first_section and first_semester:
            for s_id in request.subject_ids:
                subj = db.query(Subject).filter(Subject.id == s_id).first()
                if subj:
                    assignment = TeacherAssignment(
                        teacher_id=new_teacher.id,
                        semester_id=first_semester.id,
                        section_id=first_section.id,
                        subject_id=subj.id,
                        assignment_type="primary",
                    )
                    db.add(assignment)
                    assigned_count += 1

    db.commit()
    db.refresh(new_teacher)

    token = create_access_token({
        "sub": str(new_teacher.id),
        "college_id": new_teacher.teacher_code,
        "role": "TEACHER",
    })

    return {
        "success": True,
        "message": "Teacher registered successfully.",
        "access_token": token,
        "token_type": "bearer",
        "user_id": new_teacher.id,
        "college_id": new_teacher.teacher_code,
        "name": new_teacher.full_name,
        "email": new_teacher.email,
        "role": "TEACHER",
        "department": new_teacher.department,
        "assigned_subjects_count": assigned_count,
    }


# ==========================================
# LOGIN (STUDENT & TEACHER)
# Supports College ID or Email Address
# ==========================================

@router.post("/login", response_model=LoginResponse)
def login(
    request: LoginRequest,
    db: Session = Depends(get_db),
):
    identifier = request.college_id.strip()

    # Search by college_id or email
    student = db.query(Student).filter(
        or_(Student.student_code == identifier, Student.email == identifier.lower())
    ).first()

    teacher = db.query(Teacher).filter(
        or_(Teacher.teacher_code == identifier, Teacher.email == identifier.lower())
    ).first()

    if student and teacher:
        raise HTTPException(
            status_code=409,
            detail="Duplicate identifier found across accounts. Contact the administrator.",
        )

    if student:
        user = student
        role = "STUDENT"
        account_code = user.student_code
    elif teacher:
        user = teacher
        role = "TEACHER"
        account_code = user.teacher_code
    else:
        raise HTTPException(
            status_code=401,
            detail="Invalid College ID, Email, or password.",
        )

    if not user.is_active or not user.password_hash:
        raise HTTPException(
            status_code=401,
            detail="Invalid College ID, Email, or password.",
        )

    if not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=401,
            detail="Invalid College ID, Email, or password.",
        )

    token = create_access_token({
        "sub": str(user.id),
        "college_id": account_code,
        "role": role,
    })

    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user.id,
        "college_id": account_code,
        "name": user.full_name,
        "role": role,
        "department": getattr(user, "department", None),
        "email": user.email,
    }


# ==========================================
# LOGOUT
# ==========================================

@router.post("/logout")
def logout():
    return {"success": True, "message": "Logged out successfully."}


# ==========================================
# GET CURRENT LOGGED-IN USER
# ==========================================

@router.get("/me")
def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
):
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Authorization token required.",
        )

    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired login session.",
        )

    user_id = int(payload["sub"])
    role = payload["role"]

    if role == "STUDENT":
        user = db.query(Student).filter(Student.id == user_id).first()
    elif role == "TEACHER":
        user = db.query(Teacher).filter(Teacher.id == user_id).first()
    else:
        raise HTTPException(
            status_code=401,
            detail="Invalid account role.",
        )

    if not user or not user.is_active:
        raise HTTPException(
            status_code=401,
            detail="Account is inactive or unavailable.",
        )

    data = {
        "user_id": user.id,
        "college_id": user.student_code if role == "STUDENT" else user.teacher_code,
        "name": user.full_name,
        "email": user.email,
        "role": role,
        "department": getattr(user, "department", "Computer Science & Engineering"),
    }

    if role == "STUDENT" and user.section:
        data["section"] = user.section.code
        data["semester"] = user.section.semester.name if user.section.semester else "Semester III"
        data["academic_year"] = user.section.academic_year.name if user.section.academic_year else "Second Year"
    elif role == "TEACHER":
        data["designation"] = getattr(user, "designation", "Assistant Professor")

    return data
