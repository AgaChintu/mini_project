from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    college_id: str = Field(..., description="College ID or Registered Email Address")
    password: str = Field(..., min_length=1)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    college_id: str
    name: str
    role: str
    department: Optional[str] = None
    email: Optional[str] = None


class StudentRegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(..., min_length=6)
    confirm_password: str = Field(..., min_length=6)
    department: str = Field("Computer Science & Engineering", min_length=2)
    semester_number: int = Field(..., ge=1, le=8)
    section_code: str = Field(..., min_length=1, max_length=30)
    academic_year_number: Optional[int] = Field(None, ge=1, le=4)


class TeacherRegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(..., min_length=6)
    confirm_password: str = Field(..., min_length=6)
    department: str = Field("Computer Science & Engineering", min_length=2)
    designation: str = Field("Assistant Professor", min_length=2)
    faculty_invite_code: str = Field(..., min_length=4, description="Institutional authorization code for faculty registration")
    profile_info: Optional[str] = None
    subject_ids: Optional[List[int]] = None


class RegisterResponse(BaseModel):
    success: bool = True
    message: str
    access_token: str
    token_type: str = "bearer"
    user_id: int
    college_id: str
    name: str
    email: str
    role: str
    department: Optional[str] = None
    assigned_subjects_count: int = 0
