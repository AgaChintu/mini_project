"""
Academic Resource model for the ClariQ Library module.
Represents documents (PDF/DOC/DOCX) and YouTube links uploaded by faculty.
No RAG, no chunks, no vector embeddings — clean and decoupled.
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, Float, ForeignKey, UniqueConstraint,
)
from sqlalchemy.orm import relationship
from app.database import Base


class AcademicResource(Base):
    """
    Central library resource uploaded by a faculty member for a specific subject.
    Faculty category (PRIMARY/ADDITIONAL) is determined from SubjectTeacherAssignment.
    """
    __tablename__ = "academic_resources"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(300), nullable=False)
    description = Column(Text, nullable=True)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True)
    teacher_id = Column(Integer, ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False, index=True)
    # PRIMARY or ADDITIONAL
    faculty_category = Column(String(20), nullable=False, default="PRIMARY")
    # pdf / doc / docx / youtube
    resource_type = Column(String(20), nullable=False)
    # File storage
    storage_path = Column(Text, nullable=True)
    original_filename = Column(String(300), nullable=True)
    file_size = Column(Integer, nullable=True)
    mime_type = Column(String(100), nullable=True)
    # YouTube
    youtube_url = Column(Text, nullable=True)
    youtube_video_id = Column(String(50), nullable=True)
    youtube_thumbnail = Column(Text, nullable=True)
    youtube_title = Column(String(500), nullable=True)
    # Flags
    is_important = Column(Boolean, nullable=False, default=False)
    status = Column(String(20), nullable=False, default="active")  # active / deleted
    deleted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)

    # Relationships
    subject = relationship("Subject", foreign_keys=[subject_id])
    teacher = relationship("Teacher", foreign_keys=[teacher_id])


class DoubtCluster(Base):
    """
    Master Doubt Card — an AI-created semantic cluster of similar doubts.
    Published answers are ONLY set by authorized teachers (never auto-published by AI).
    """
    __tablename__ = "doubt_clusters"

    id = Column(Integer, primary_key=True, index=True)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True, index=True)
    teacher_id = Column(Integer, ForeignKey("teachers.id", ondelete="SET NULL"), nullable=True, index=True)
    cluster_title = Column(String(300), nullable=False)
    ai_summary = Column(Text, nullable=True)
    keywords = Column(Text, nullable=True)  # comma-separated
    topic = Column(String(200), nullable=True)
    # Priority
    ai_priority = Column(String(20), nullable=False, default="medium")  # high/medium/low
    teacher_priority = Column(String(20), nullable=True)
    priority_reason = Column(Text, nullable=True)
    # Status
    status = Column(String(30), nullable=False, default="pending")
    # AI-generated draft (never auto-published)
    ai_draft_answer = Column(Text, nullable=True)
    teacher_edited_answer = Column(Text, nullable=True)
    # Published answer — set ONLY by teacher action
    published_answer = Column(Text, nullable=True)
    published_at = Column(DateTime, nullable=True)
    published_by_teacher_id = Column(Integer, ForeignKey("teachers.id", ondelete="SET NULL"), nullable=True)
    doubt_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)

    # Relationships
    subject = relationship("Subject", foreign_keys=[subject_id])
    teacher = relationship("Teacher", foreign_keys=[teacher_id])
    published_by = relationship("Teacher", foreign_keys=[published_by_teacher_id])
    members = relationship(
        "DoubtClusterMember",
        back_populates="cluster",
        cascade="all, delete-orphan",
    )


class DoubtClusterMember(Base):
    """Links individual student doubts to a DoubtCluster (Master Card)."""
    __tablename__ = "doubt_cluster_members"
    __table_args__ = (
        UniqueConstraint("cluster_id", "doubt_id", name="uq_cluster_doubt"),
    )

    id = Column(Integer, primary_key=True, index=True)
    cluster_id = Column(Integer, ForeignKey("doubt_clusters.id", ondelete="CASCADE"), nullable=False, index=True)
    doubt_id = Column(Integer, ForeignKey("doubts.id", ondelete="CASCADE"), nullable=False, index=True)
    similarity_score = Column(Float, nullable=True)
    added_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    added_by = Column(String(20), nullable=False, default="ai")  # 'ai' or 'teacher'

    # Relationships
    cluster = relationship("DoubtCluster", back_populates="members")
    doubt = relationship("Doubt")
