from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    student_code = Column(String(50), nullable=False, unique=True, index=True)  # college/student ID
    full_name = Column(String(150), nullable=False)
    email = Column(String(255), nullable=True, unique=True, index=True)
    password_hash = Column(String(255), nullable=True)
    department = Column(String(100), nullable=True, default="Computer Science & Engineering")
    current_semester = Column(Integer, nullable=True, index=True)  # 1 to 8
    section_id = Column(Integer, ForeignKey("sections.id"), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)

    # Relationships
    section = relationship("Section", back_populates="students")
    doubts = relationship("Doubt", back_populates="student", cascade="all, delete-orphan", passive_deletes=True)
    saved_entries = relationship("SavedEntry", back_populates="student", cascade="all, delete-orphan", passive_deletes=True)
    session_doubts = relationship("SessionDoubt", back_populates="student", cascade="all, delete-orphan", passive_deletes=True)


class Teacher(Base):
    __tablename__ = "teachers"

    id = Column(Integer, primary_key=True, index=True)
    teacher_code = Column(String(50), nullable=False, unique=True, index=True)
    full_name = Column(String(150), nullable=False)
    email = Column(String(255), nullable=True, unique=True, index=True)
    password_hash = Column(String(255), nullable=True)
    department = Column(String(100), nullable=True, default="Computer Science & Engineering")
    designation = Column(String(100), nullable=True, default="Assistant Professor")
    profile_info = Column(String(500), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)

    # Relationships
    assignments = relationship("TeacherAssignment", back_populates="teacher", cascade="all, delete-orphan")
    subject_faculty_assignments = relationship("SubjectTeacherAssignment", back_populates="teacher", cascade="all, delete-orphan")
    answers = relationship("DoubtAnswer", back_populates="teacher")
    published_library_entries = relationship("LibraryEntry", back_populates="published_by")
    sessions = relationship("DoubtSession", back_populates="teacher")
