from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from app.database import Base


class AcademicYear(Base):
    __tablename__ = "academic_years"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, unique=True)  # e.g., "First Year", "Second Year"
    year_number = Column(Integer, nullable=False, unique=True)  # 1, 2
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Bidirectional relationships
    semesters = relationship(
        "Semester",
        back_populates="academic_year",
        cascade="all, delete-orphan",
        order_by="Semester.semester_number",
    )
    section_groups = relationship(
        "SectionGroup",
        back_populates="academic_year",
        cascade="all, delete-orphan",
    )
    sections = relationship(
        "Section",
        back_populates="academic_year",
        cascade="all, delete-orphan",
    )


class Semester(Base):
    __tablename__ = "semesters"
    __table_args__ = (
        UniqueConstraint("academic_year_id", "semester_number", name="uq_year_semester"),
    )

    id = Column(Integer, primary_key=True, index=True)
    academic_year_id = Column(Integer, ForeignKey("academic_years.id"), nullable=False)
    semester_number = Column(Integer, nullable=False)  # 1 to 4
    name = Column(String(50), nullable=False)  # "Semester I", "Semester III"

    # Relationships
    academic_year = relationship("AcademicYear", back_populates="semesters")
    sections = relationship("Section", back_populates="semester")
    section_groups = relationship("SectionGroup", back_populates="semester")
    subject_offerings = relationship(
        "SubjectOffering",
        back_populates="semester",
        cascade="all, delete-orphan",
    )


class SectionGroup(Base):
    __tablename__ = "section_groups"

    id = Column(Integer, primary_key=True, index=True)
    academic_year_id = Column(Integer, ForeignKey("academic_years.id"), nullable=False)
    semester_id = Column(Integer, ForeignKey("semesters.id"), nullable=True)
    code = Column(String(50), nullable=False, unique=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)

    # Relationships
    academic_year = relationship("AcademicYear", back_populates="section_groups")
    semester = relationship("Semester", back_populates="section_groups")
    members = relationship(
        "SectionGroupMember",
        back_populates="section_group",
        cascade="all, delete-orphan",
    )
    subject_offerings = relationship(
        "SubjectOffering",
        back_populates="section_group",
        cascade="all, delete-orphan",
    )


class Section(Base):
    __tablename__ = "sections"
    __table_args__ = (
        UniqueConstraint("academic_year_id", "code", name="uq_year_section"),
    )

    id = Column(Integer, primary_key=True, index=True)
    academic_year_id = Column(Integer, ForeignKey("academic_years.id"), nullable=False)
    semester_id = Column(Integer, ForeignKey("semesters.id"), nullable=True)
    code = Column(String(30), nullable=False)  # AIML, CS1, 2-AIML
    name = Column(String(100), nullable=False)

    # Relationships
    academic_year = relationship("AcademicYear", back_populates="sections")
    semester = relationship("Semester", back_populates="sections")
    students = relationship("Student", back_populates="section")
    group_memberships = relationship(
        "SectionGroupMember",
        back_populates="section",
        cascade="all, delete-orphan",
    )


class SectionGroupMember(Base):
    __tablename__ = "section_group_members"
    __table_args__ = (
        UniqueConstraint("section_group_id", "section_id", name="uq_group_section"),
    )

    id = Column(Integer, primary_key=True, index=True)
    section_group_id = Column(Integer, ForeignKey("section_groups.id"), nullable=False)
    section_id = Column(Integer, ForeignKey("sections.id"), nullable=False)

    # Relationships
    section_group = relationship("SectionGroup", back_populates="members")
    section = relationship("Section", back_populates="group_memberships")


class Subject(Base):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(30), nullable=True, unique=True, index=True)
    name = Column(String(150), nullable=False)
    subject_type = Column(String(30), nullable=True)  # theory, lab
    description = Column(Text, nullable=True)
    # Extended metadata for admin management
    department = Column(String(100), nullable=True, default="Computer Science & Engineering")
    semester_label = Column(String(50), nullable=True)   # e.g. "III", "IV"
    semester_number = Column(Integer, nullable=True, index=True)  # 1 to 8
    academic_year_label = Column(String(50), nullable=True)  # e.g. "Second Year"
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=True, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)

    # Relationships
    offerings = relationship("SubjectOffering", back_populates="subject", cascade="all, delete-orphan")
    syllabus_units = relationship(
        "SyllabusUnit",
        back_populates="subject",
        cascade="all, delete-orphan",
        order_by="SyllabusUnit.unit_number",
    )
    course_outcomes = relationship("CourseOutcome", back_populates="subject", cascade="all, delete-orphan")
    textbooks = relationship("Textbook", back_populates="subject", cascade="all, delete-orphan")
    faculty_assignments = relationship(
        "SubjectTeacherAssignment",
        back_populates="subject",
        cascade="all, delete-orphan",
    )


class SubjectOffering(Base):
    __tablename__ = "subject_offerings"
    __table_args__ = (
        UniqueConstraint("semester_id", "section_group_id", "subject_id", name="uq_subject_offering"),
    )

    id = Column(Integer, primary_key=True, index=True)
    semester_id = Column(Integer, ForeignKey("semesters.id"), nullable=False)
    section_group_id = Column(Integer, ForeignKey("section_groups.id"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    lecture_hours = Column(Integer, nullable=True)
    tutorial_hours = Column(Integer, nullable=True)
    practical_hours = Column(Integer, nullable=True)

    # Relationships
    semester = relationship("Semester", back_populates="subject_offerings")
    section_group = relationship("SectionGroup", back_populates="subject_offerings")
    subject = relationship("Subject", back_populates="offerings")


class SyllabusUnit(Base):
    __tablename__ = "syllabus_units"
    __table_args__ = (
        UniqueConstraint("subject_id", "unit_number", name="uq_subject_unit"),
    )

    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    unit_number = Column(Integer, nullable=False)
    unit_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    proposed_lectures = Column(Integer, nullable=True)

    # Relationships
    subject = relationship("Subject", back_populates="syllabus_units")
    topics = relationship(
        "SyllabusTopic",
        back_populates="unit",
        cascade="all, delete-orphan",
        order_by="SyllabusTopic.display_order",
    )


class SyllabusTopic(Base):
    __tablename__ = "syllabus_topics"

    id = Column(Integer, primary_key=True, index=True)
    unit_id = Column(Integer, ForeignKey("syllabus_units.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    display_order = Column(Integer, nullable=False, default=1)

    # Relationships
    unit = relationship("SyllabusUnit", back_populates="topics")
    subtopics = relationship(
        "SyllabusSubtopic",
        back_populates="topic",
        cascade="all, delete-orphan",
        order_by="SyllabusSubtopic.display_order",
    )


class SyllabusSubtopic(Base):
    __tablename__ = "syllabus_subtopics"

    id = Column(Integer, primary_key=True, index=True)
    topic_id = Column(Integer, ForeignKey("syllabus_topics.id"), nullable=False)
    name = Column(String(255), nullable=False)
    display_order = Column(Integer, nullable=False, default=1)

    # Relationships
    topic = relationship("SyllabusTopic", back_populates="subtopics")


class CourseOutcome(Base):
    __tablename__ = "course_outcomes"
    __table_args__ = (
        UniqueConstraint("subject_id", "co_number", name="uq_subject_co"),
    )

    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    co_number = Column(Integer, nullable=False)
    description = Column(Text, nullable=False)
    bloom_levels = Column(String(50), nullable=True)

    # Relationships
    subject = relationship("Subject", back_populates="course_outcomes")


class Textbook(Base):
    __tablename__ = "textbooks"

    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    title = Column(String(500), nullable=False)
    authors = Column(String(500), nullable=True)
    publisher = Column(String(255), nullable=True)
    edition = Column(String(100), nullable=True)
    book_type = Column(String(30), nullable=True)  # textbook / reference
    display_order = Column(Integer, nullable=False, default=1)

    # Relationships
    subject = relationship("Subject", back_populates="textbooks")
