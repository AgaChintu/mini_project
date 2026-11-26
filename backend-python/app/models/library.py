from datetime import datetime
from sqlalchemy import Column, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class LibraryEntry(Base):
    """
    Published repository of resolved doubts curated by teachers.
    References the original resolved doubt and answers without unnecessary data duplication.
    """
    __tablename__ = "library_entries"

    id = Column(Integer, primary_key=True, index=True)
    doubt_id = Column(Integer, ForeignKey("doubts.id"), nullable=False, unique=True)
    published_by_teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=False)
    published_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    doubt = relationship("Doubt", back_populates="library_entry")
    published_by = relationship("Teacher", back_populates="published_library_entries")
    saved_by_students = relationship(
        "SavedEntry",
        back_populates="library_entry",
        cascade="all, delete-orphan",
    )


class SavedEntry(Base):
    """
    Bookmarks/saves made by students for library entries.
    Enforces a unique constraint to prevent duplicate saves.
    """
    __tablename__ = "saved_entries"
    __table_args__ = (
        UniqueConstraint("student_id", "library_entry_id", name="uq_student_saved_entry"),
    )

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    library_entry_id = Column(Integer, ForeignKey("library_entries.id"), nullable=False)
    saved_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    student = relationship("Student", back_populates="saved_entries")
    library_entry = relationship("LibraryEntry", back_populates="saved_by_students")
