from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    Boolean,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from app.database import Base


class Doubt(Base):
    """
    Academic doubt model submitted by students.
    Supports both modern 'title' & 'description' fields and legacy 'question' field
    for full backward compatibility with existing frontends and seed scripts.
    """
    __tablename__ = "doubts"

    id = Column(Integer, primary_key=True, index=True)
    doubt_code = Column(String(36), nullable=False, unique=True, index=True)

    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    section_id = Column(Integer, ForeignKey("sections.id"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=True)
    topic_id = Column(Integer, ForeignKey("syllabus_topics.id"), nullable=True)
    subtopic_id = Column(Integer, ForeignKey("syllabus_subtopics.id"), nullable=True)

    # Modern form fields
    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)

    # Legacy field preserved for full backward compatibility
    question = Column(Text, nullable=False)

    # Status: pending, in_progress, resolved
    status = Column(String(30), nullable=False, default="pending", index=True)
    is_anonymous_to_teacher = Column(Boolean, nullable=False, default=True)

    # AI-generated fields for teacher dashboard & clustering
    ai_summary = Column(Text, nullable=True)
    keywords = Column(String(500), nullable=True)
    cluster_title = Column(String(255), nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)

    # Relationships
    student = relationship("Student", back_populates="doubts")
    section = relationship("Section")
    subject = relationship("Subject")
    teacher = relationship("Teacher")
    topic = relationship("SyllabusTopic")
    subtopic = relationship("SyllabusSubtopic")

    subtopic_mappings = relationship(
        "DoubtSubtopic",
        back_populates="doubt",
        cascade="all, delete-orphan",
    )
    answers = relationship(
        "DoubtAnswer",
        back_populates="doubt",
        cascade="all, delete-orphan",
        order_by="DoubtAnswer.created_at",
    )
    attachments = relationship(
        "Attachment",
        back_populates="doubt",
        cascade="all, delete-orphan",
    )
    library_entry = relationship(
        "LibraryEntry",
        back_populates="doubt",
        uselist=False,
        cascade="all, delete-orphan",
    )


class DoubtSubtopic(Base):
    __tablename__ = "doubt_subtopics"
    __table_args__ = (
        UniqueConstraint("doubt_id", "subtopic_id", name="uq_doubt_subtopic"),
    )

    id = Column(Integer, primary_key=True, index=True)
    doubt_id = Column(Integer, ForeignKey("doubts.id", ondelete="CASCADE"), nullable=False)
    subtopic_id = Column(Integer, ForeignKey("syllabus_subtopics.id"), nullable=False)

    # Relationships
    doubt = relationship("Doubt", back_populates="subtopic_mappings")
    subtopic = relationship("SyllabusSubtopic")


class DoubtAnswer(Base):
    __tablename__ = "doubt_answers"

    id = Column(Integer, primary_key=True, index=True)
    doubt_id = Column(Integer, ForeignKey("doubts.id", ondelete="CASCADE"), nullable=False)
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=False)
    answer_text = Column(Text, nullable=False)
    resource_url = Column(String(1000), nullable=True)
    # Teacher solution file attachment fields
    answer_attachment_path = Column(String(1000), nullable=True)
    answer_attachment_name = Column(String(255), nullable=True)
    answer_attachment_mime = Column(String(100), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)

    # Relationships
    doubt = relationship("Doubt", back_populates="answers")
    teacher = relationship("Teacher", back_populates="answers")


class Attachment(Base):
    __tablename__ = "attachments"

    id = Column(Integer, primary_key=True, index=True)
    doubt_id = Column(Integer, ForeignKey("doubts.id", ondelete="CASCADE"), nullable=False)
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False, unique=True)
    mime_type = Column(String(100), nullable=False)
    file_size = Column(Integer, nullable=False)
    storage_path = Column(String(1000), nullable=False)
    uploaded_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    doubt = relationship("Doubt", back_populates="attachments")
