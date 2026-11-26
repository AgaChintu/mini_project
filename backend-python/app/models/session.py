from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class DoubtSession(Base):
    """
    Structured doubt-clearing sessions scheduled by teachers for specific sections and subjects.
    """
    __tablename__ = "doubt_sessions"

    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=False)
    section_id = Column(Integer, ForeignKey("sections.id"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)

    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    session_date = Column(DateTime, nullable=True)
    starts_at = Column(DateTime, nullable=True)
    ends_at = Column(DateTime, nullable=True)

    submission_opens_at = Column(DateTime, nullable=False)
    submission_closes_at = Column(DateTime, nullable=False)

    # Status: upcoming, active, completed, cancelled
    status = Column(String(30), nullable=False, default="upcoming", index=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    teacher = relationship("Teacher", back_populates="sessions")
    section = relationship("Section")
    subject = relationship("Subject")
    topics = relationship(
        "SessionTopic",
        back_populates="session",
        cascade="all, delete-orphan",
    )
    doubts = relationship(
        "SessionDoubt",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="SessionDoubt.created_at",
    )


class SessionTopic(Base):
    """
    Topics covered in a specific doubt session.
    """
    __tablename__ = "session_topics"
    __table_args__ = (
        UniqueConstraint("session_id", "topic_id", name="uq_session_topic"),
    )

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("doubt_sessions.id"), nullable=False)
    topic_id = Column(Integer, ForeignKey("syllabus_topics.id"), nullable=False)

    # Relationships
    session = relationship("DoubtSession", back_populates="topics")
    topic = relationship("SyllabusTopic")


class SessionDoubt(Base):
    """
    Doubt submitted by a student specifically for an active doubt session.
    Kept distinct from normal academic doubts.
    """
    __tablename__ = "session_doubts"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("doubt_sessions.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    topic_id = Column(Integer, ForeignKey("syllabus_topics.id"), nullable=False)
    question = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)
    is_edited = Column(Boolean, nullable=False, default=False)

    # Relationships
    session = relationship("DoubtSession", back_populates="doubts")
    student = relationship("Student", back_populates="session_doubts")
    topic = relationship("SyllabusTopic")
