from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.common import APIResponse
from app.schemas.academic import (
    AcademicYearOut,
    SemesterOut,
    SectionOut,
    SubjectOut,
    SyllabusUnitOut,
    SyllabusTopicOut,
    SyllabusSubtopicOut,
)
from app.models.academic import (
    AcademicYear,
    Semester,
    Section,
    Subject,
    SubjectOffering,
    SectionGroupMember,
    SyllabusUnit,
    SyllabusTopic,
    SyllabusSubtopic,
)

router = APIRouter(prefix="/api/academic", tags=["Academic Structure"])


@router.get("/years", response_model=APIResponse[List[AcademicYearOut]])
def get_academic_years(db: Session = Depends(get_db)):
    """Fetch all academic years."""
    years = db.query(AcademicYear).order_by(AcademicYear.year_number).all()
    return APIResponse(
        success=True,
        message="Academic years retrieved successfully",
        data=years,
    )


@router.get("/semesters", response_model=APIResponse[List[SemesterOut]])
def get_semesters(
    academic_year_id: Optional[int] = Query(None, description="Filter by Academic Year ID"),
    db: Session = Depends(get_db),
):
    """Fetch semesters, optionally filtered by academic year."""
    query = db.query(Semester)
    if academic_year_id is not None:
        query = query.filter(Semester.academic_year_id == academic_year_id)
    semesters = query.order_by(Semester.semester_number).all()
    return APIResponse(
        success=True,
        message="Semesters retrieved successfully",
        data=semesters,
    )


@router.get("/sections", response_model=APIResponse[List[SectionOut]])
def get_sections(
    academic_year_id: Optional[int] = Query(None, description="Filter by Academic Year ID"),
    semester_id: Optional[int] = Query(None, description="Filter by Semester ID"),
    db: Session = Depends(get_db),
):
    """Fetch sections with optional filtering by year and semester."""
    query = db.query(Section)
    if academic_year_id is not None:
        query = query.filter(Section.academic_year_id == academic_year_id)
    if semester_id is not None:
        query = query.filter(Section.semester_id == semester_id)
    sections = query.order_by(Section.code).all()
    return APIResponse(
        success=True,
        message="Sections retrieved successfully",
        data=sections,
    )


@router.get("/subjects", response_model=APIResponse[List[SubjectOut]])
def get_subjects(
    semester_id: Optional[int] = Query(None, description="Filter by Semester ID"),
    section_id: Optional[int] = Query(None, description="Filter by Section ID"),
    db: Session = Depends(get_db),
):
    """
    Fetch subjects offered, with optional filters for semester or section.
    If section_id is provided, resolves subjects mapped via section group offerings.
    """
    if section_id is not None:
        query = (
            db.query(Subject)
            .join(SubjectOffering, SubjectOffering.subject_id == Subject.id)
            .join(
                SectionGroupMember,
                SectionGroupMember.section_group_id == SubjectOffering.section_group_id,
            )
            .filter(SectionGroupMember.section_id == section_id)
        )
        if semester_id is not None:
            query = query.filter(SubjectOffering.semester_id == semester_id)
        subjects = query.distinct().order_by(Subject.name).all()
    elif semester_id is not None:
        subjects = (
            db.query(Subject)
            .join(SubjectOffering, SubjectOffering.subject_id == Subject.id)
            .filter(SubjectOffering.semester_id == semester_id)
            .distinct()
            .order_by(Subject.name)
            .all()
        )
    else:
        subjects = db.query(Subject).order_by(Subject.name).all()

    return APIResponse(
        success=True,
        message="Subjects retrieved successfully",
        data=subjects,
    )


@router.get("/subjects/{subject_id}/units", response_model=APIResponse[List[SyllabusUnitOut]])
def get_subject_units(subject_id: int, db: Session = Depends(get_db)):
    """Fetch syllabus units for a specific subject."""
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject with ID {subject_id} was not found",
        )
    units = (
        db.query(SyllabusUnit)
        .filter(SyllabusUnit.subject_id == subject_id)
        .order_by(SyllabusUnit.unit_number)
        .all()
    )
    return APIResponse(
        success=True,
        message=f"Syllabus units for subject {subject.name} retrieved successfully",
        data=units,
    )


@router.get("/units/{unit_id}/topics", response_model=APIResponse[List[SyllabusTopicOut]])
def get_unit_topics(unit_id: int, db: Session = Depends(get_db)):
    """Fetch syllabus topics for a specific unit."""
    unit = db.query(SyllabusUnit).filter(SyllabusUnit.id == unit_id).first()
    if not unit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unit with ID {unit_id} was not found",
        )
    topics = (
        db.query(SyllabusTopic)
        .filter(SyllabusTopic.unit_id == unit_id)
        .order_by(SyllabusTopic.display_order)
        .all()
    )
    return APIResponse(
        success=True,
        message=f"Topics for unit {unit.unit_name} retrieved successfully",
        data=topics,
    )


@router.get("/topics/{topic_id}/subtopics", response_model=APIResponse[List[SyllabusSubtopicOut]])
def get_topic_subtopics(topic_id: int, db: Session = Depends(get_db)):
    """Fetch syllabus subtopics for a specific topic."""
    topic = db.query(SyllabusTopic).filter(SyllabusTopic.id == topic_id).first()
    if not topic:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Topic with ID {topic_id} was not found",
        )
    subtopics = (
        db.query(SyllabusSubtopic)
        .filter(SyllabusSubtopic.topic_id == topic_id)
        .order_by(SyllabusSubtopic.display_order)
        .all()
    )
    return APIResponse(
        success=True,
        message=f"Subtopics for topic '{topic.name}' retrieved successfully",
        data=subtopics,
    )
