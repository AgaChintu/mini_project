# ClariQ Models Registry
# Imports every model so SQLAlchemy metadata registers all tables and relationships.

from app.models.academic import (
    AcademicYear,
    Semester,
    SectionGroup,
    Section,
    SectionGroupMember,
    Subject,
    SubjectOffering,
    SyllabusUnit,
    SyllabusTopic,
    SyllabusSubtopic,
    CourseOutcome,
    Textbook,
)

from app.models.user import (
    Student,
    Teacher,
)

from app.models.assignment import (
    TeacherAssignment,
    SubjectTeacherAssignment,
)

from app.models.admin import (
    Admin,
)

from app.models.doubt import (
    Doubt,
    DoubtSubtopic,
    DoubtAnswer,
    Attachment,
)

from app.models.library import (
    LibraryEntry,
    SavedEntry,
)

from app.models.academic_resource import (
    AcademicResource,
    DoubtCluster,
    DoubtClusterMember,
)

from app.models.session import (
    DoubtSession,
    SessionTopic,
    SessionDoubt,
)

from app.models.chatbot import (
    ChatConversation,
    ChatMessage,
)

__all__ = [
    "AcademicYear",
    "Semester",
    "SectionGroup",
    "Section",
    "SectionGroupMember",
    "Subject",
    "SubjectOffering",
    "SyllabusUnit",
    "SyllabusTopic",
    "SyllabusSubtopic",
    "CourseOutcome",
    "Textbook",
    "Student",
    "Teacher",
    "TeacherAssignment",
    "SubjectTeacherAssignment",
    "Admin",
    "Doubt",
    "DoubtSubtopic",
    "DoubtAnswer",
    "Attachment",
    "LibraryEntry",
    "SavedEntry",
    "AcademicResource",
    "DoubtCluster",
    "DoubtClusterMember",
    "DoubtSession",
    "SessionTopic",
    "SessionDoubt",
    "ChatConversation",
    "ChatMessage",
]
