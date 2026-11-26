import pytest
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from app.models import (
    AcademicYear,
    Semester,
    Section,
    Subject,
    SyllabusUnit,
    SyllabusTopic,
    SyllabusSubtopic,
    Student,
    Teacher,
    Doubt,
    DoubtAnswer,
    LibraryEntry,
    SavedEntry,
)


def test_academic_hierarchy_relationships(db_session):
    # 1. AcademicYear
    year = AcademicYear(name="Test Year 1", year_number=101, is_active=True)
    db_session.add(year)
    db_session.commit()

    # 2. Semester
    sem = Semester(academic_year_id=year.id, semester_number=1, name="Test Sem 1")
    db_session.add(sem)
    db_session.commit()

    # 3. Section
    sec = Section(academic_year_id=year.id, semester_id=sem.id, code="T-AIML", name="Test AIML")
    db_session.add(sec)
    db_session.commit()

    # 4. Subject
    subj = Subject(code="TEST101", name="Test Subject", subject_type="theory")
    db_session.add(subj)
    db_session.commit()

    # 5. SyllabusUnit
    unit = SyllabusUnit(subject_id=subj.id, unit_number=1, unit_name="Unit 1 - Intro")
    db_session.add(unit)
    db_session.commit()

    # 6. SyllabusTopic
    topic = SyllabusTopic(unit_id=unit.id, name="Topic 1.1", display_order=1)
    db_session.add(topic)
    db_session.commit()

    # 7. SyllabusSubtopic
    subtopic = SyllabusSubtopic(topic_id=topic.id, name="Subtopic 1.1.1", display_order=1)
    db_session.add(subtopic)
    db_session.commit()

    # Verify relationships
    assert sem.academic_year.name == "Test Year 1"
    assert len(year.semesters) >= 1
    assert sec.semester.name == "Test Sem 1"
    assert unit.subject.code == "TEST101"
    assert topic.unit.unit_name == "Unit 1 - Intro"
    assert subtopic.topic.name == "Topic 1.1"


def test_unique_constraint_academic_year(db_session):
    year1 = AcademicYear(name="Duplicate Year", year_number=901)
    db_session.add(year1)
    db_session.commit()

    year2 = AcademicYear(name="Duplicate Year", year_number=902)
    db_session.add(year2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_user_and_doubt_models(db_session):
    year = AcademicYear(name="User Test Year", year_number=905)
    db_session.add(year)
    db_session.flush()

    sem = Semester(academic_year_id=year.id, semester_number=1, name="Sem 1")
    db_session.add(sem)
    db_session.flush()

    sec = Section(academic_year_id=year.id, semester_id=sem.id, code="SEC-U", name="Section U")
    db_session.add(sec)
    db_session.flush()

    subj = Subject(code="SUBJ-U", name="Subject U")
    db_session.add(subj)
    db_session.flush()

    student = Student(student_code="STU_99", full_name="Student Test", section_id=sec.id)
    teacher = Teacher(teacher_code="TCH_99", full_name="Teacher Test")
    db_session.add_all([student, teacher])
    db_session.flush()

    doubt = Doubt(
        doubt_code="uuid-doubt-test-01",
        student_id=student.id,
        section_id=sec.id,
        subject_id=subj.id,
        teacher_id=teacher.id,
        title="Sample Doubt Title",
        description="Sample Description",
        question="Sample Question",
        status="pending",
    )
    db_session.add(doubt)
    db_session.flush()

    answer = DoubtAnswer(
        doubt_id=doubt.id,
        teacher_id=teacher.id,
        answer_text="Here is the explanation.",
    )
    db_session.add(answer)
    db_session.flush()

    assert len(doubt.answers) == 1
    assert doubt.answers[0].answer_text == "Here is the explanation."
    assert doubt.student.student_code == "STU_99"
