from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class AcademicYearOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    year_number: int
    is_active: bool
    created_at: datetime


class SemesterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    academic_year_id: int
    semester_number: int
    name: str


class SectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    academic_year_id: int
    semester_id: Optional[int] = None
    code: str
    name: str


class SubjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: Optional[str] = None
    name: str
    subject_type: Optional[str] = None
    description: Optional[str] = None


class SyllabusSubtopicOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    topic_id: int
    name: str
    display_order: int


class SyllabusTopicOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    unit_id: int
    name: str
    description: Optional[str] = None
    display_order: int
    subtopics: Optional[List[SyllabusSubtopicOut]] = None


class SyllabusUnitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    subject_id: int
    unit_number: int
    unit_name: str
    description: Optional[str] = None
    proposed_lectures: Optional[int] = None
    topics: Optional[List[SyllabusTopicOut]] = None
