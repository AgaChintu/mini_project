from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class TeacherAssignment(Base):
    """
    Section-specific teacher assignment.
    Preserved for backward compatibility.
    """
    __tablename__ = "teacher_assignments"
    __table_args__ = (
        UniqueConstraint(
            "teacher_id",
            "semester_id",
            "section_id",
            "subject_id",
            name="uq_teacher_semester_section_subject",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=False)
    semester_id = Column(Integer, ForeignKey("semesters.id"), nullable=False)
    section_id = Column(Integer, ForeignKey("sections.id"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    assignment_type = Column(String(50), nullable=True, default="primary")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    teacher = relationship("Teacher", back_populates="assignments")
    semester = relationship("Semester")
    section = relationship("Section")
    subject = relationship("Subject")


class SubjectTeacherAssignment(Base):
    """
    Direct many-to-many assignment between Subject and Teacher.
    Allows multiple faculty members per subject, with one designated Primary Faculty.
    """
    __tablename__ = "subject_teacher_assignments"
    __table_args__ = (
        UniqueConstraint("subject_id", "teacher_id", name="uq_subject_teacher_direct"),
    )

    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True)
    teacher_id = Column(Integer, ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False, index=True)
    is_primary = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    assigned_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    assigned_by_admin_id = Column(Integer, ForeignKey("admins.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    subject = relationship("Subject", back_populates="faculty_assignments")
    teacher = relationship("Teacher", back_populates="subject_faculty_assignments")
    assigned_by = relationship("Admin")
