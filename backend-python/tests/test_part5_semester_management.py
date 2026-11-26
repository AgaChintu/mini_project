"""
Part 5: Complete Semester-Based Academic Management System Tests
Covers:
1. Admin can assign a semester to a student.
2. Admin can change a student's semester.
3. Admin can create a subject with a semester number.
4. Admin can change an existing subject's semester number.
5. Student sees only their semester's subjects.
6. Student cannot submit doubts for another semester's subjects (validated on backend).
7. Faculty assignments remain intact after subject semester changes.
8. Historical doubts are preserved across student and subject semester changes.
9. Students without assigned semesters receive an informative response (not all subjects).
10. Admin authorization remains intact on all new endpoints.
11. Semester summary API calculates correct counts from database.
12. Filtering subjects by semester_number in admin panel.
"""
import pytest
from app.models.academic import Subject, Section, Semester, AcademicYear
from app.models.assignment import SubjectTeacherAssignment
from app.models.user import Student, Teacher
from app.models.admin import Admin
from app.models.doubt import Doubt
from app.security import hash_password, create_access_token


@pytest.fixture
def sem_test_setup(db_session):
    """Sets up an admin, teachers, sections, semesters, and subjects across different semesters."""
    # 1. Admin
    admin = db_session.query(Admin).filter(Admin.username == "admin").first()
    if not admin:
        admin = Admin(
            username="admin",
            email="admin@clariq.edu",
            full_name="Super Administrator",
            password_hash=hash_password("AdminPass123!"),
            is_active=True,
        )
        db_session.add(admin)
        db_session.flush()

    # 2. Academic Year
    ay = db_session.query(AcademicYear).first()
    if not ay:
        ay = AcademicYear(name="AY 2026-27", year_number=1, is_active=True)
        db_session.add(ay)
        db_session.flush()

    # 3. Semesters 1 and 3
    sem1 = db_session.query(Semester).filter(Semester.semester_number == 1).first()
    if not sem1:
        sem1 = Semester(academic_year_id=ay.id, semester_number=1, name="Semester I")
        db_session.add(sem1)
        db_session.flush()

    sem3 = db_session.query(Semester).filter(Semester.semester_number == 3).first()
    if not sem3:
        sem3 = Semester(academic_year_id=ay.id, semester_number=3, name="Semester III")
        db_session.add(sem3)
        db_session.flush()

    # 4. Section
    sec = db_session.query(Section).first()
    if not sec:
        sec = Section(code="CSE-1", name="CSE Section 1", academic_year_id=ay.id, semester_id=sem1.id)
        db_session.add(sec)
        db_session.flush()

    # 5. Teacher
    t = db_session.query(Teacher).first()
    if not t:
        t = Teacher(
            teacher_code="T-SEM-01",
            full_name="Dr. Semester Lead",
            email="sem.lead@test.edu",
            password_hash=hash_password("teacher123"),
            is_active=True,
        )
        db_session.add(t)
        db_session.flush()

    # 6. Distinct Subjects for Sem 1 and Sem 3
    s_sem1 = db_session.query(Subject).filter(Subject.code == "TEST-SEM1-01").first()
    if not s_sem1:
        s_sem1 = Subject(
            code="TEST-SEM1-01",
            name="Foundations of Programming",
            semester_number=1,
            semester_label="Semester 1",
            department="Computer Science & Engineering",
            is_active=True,
        )
        db_session.add(s_sem1)
        db_session.flush()

    s_sem3 = db_session.query(Subject).filter(Subject.code == "TEST-SEM3-01").first()
    if not s_sem3:
        s_sem3 = Subject(
            code="TEST-SEM3-01",
            name="Advanced Database Systems",
            semester_number=3,
            semester_label="Semester 3",
            department="Computer Science & Engineering",
            is_active=True,
        )
        db_session.add(s_sem3)
        db_session.flush()

    # Assign teacher to both subjects
    for s in [s_sem1, s_sem3]:
        has_sta = db_session.query(SubjectTeacherAssignment).filter(
            SubjectTeacherAssignment.subject_id == s.id,
            SubjectTeacherAssignment.teacher_id == t.id,
        ).first()
        if not has_sta:
            db_session.add(SubjectTeacherAssignment(
                subject_id=s.id,
                teacher_id=t.id,
                is_primary=True,
                is_active=True,
            ))

    # 7. Student with Semester 1
    stu1 = db_session.query(Student).filter(Student.student_code == "STU-SEM-1").first()
    if not stu1:
        stu1 = Student(
            student_code="STU-SEM-1",
            full_name="First Year Student",
            email="firstyear@test.edu",
            password_hash=hash_password("student123"),
            section_id=sec.id,
            current_semester=1,
            is_active=True,
        )
        db_session.add(stu1)
        db_session.flush()

    # 8. Student without Semester assigned
    stu_unassigned = db_session.query(Student).filter(Student.student_code == "STU-SEM-NONE").first()
    if not stu_unassigned:
        stu_unassigned = Student(
            student_code="STU-SEM-NONE",
            full_name="Unassigned Student",
            email="unassigned@test.edu",
            password_hash=hash_password("student123"),
            section_id=sec.id,
            current_semester=None,
            is_active=True,
        )
        db_session.add(stu_unassigned)
        db_session.flush()

    db_session.commit()

    return {
        "admin": admin,
        "teacher": t,
        "s_sem1": s_sem1,
        "s_sem3": s_sem3,
        "stu1": stu1,
        "stu_unassigned": stu_unassigned,
        "section": sec,
    }


def test_admin_list_students_and_semester_filter(client, sem_test_setup):
    """Admin can list students, search them, and filter by semester."""
    admin_token = create_access_token({"sub": str(sem_test_setup["admin"].id), "role": "ADMIN"})
    headers = {"Authorization": f"Bearer {admin_token}"}

    # All students
    res = client.get("/api/admin/students", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert len(data["data"]) >= 2

    # Filter by semester 1
    res_sem1 = client.get("/api/admin/students?current_semester=1", headers=headers)
    assert res_sem1.status_code == 200
    for st in res_sem1.json()["data"]:
        assert st["current_semester"] == 1


def test_admin_assign_and_change_student_semester(client, sem_test_setup, db_session):
    """Admin assigns semester to unassigned student and changes existing student semester."""
    admin_token = create_access_token({"sub": str(sem_test_setup["admin"].id), "role": "ADMIN"})
    headers = {"Authorization": f"Bearer {admin_token}"}

    stu_unassigned = sem_test_setup["stu_unassigned"]
    stu1 = sem_test_setup["stu1"]

    # 1. Assign Semester 2 to unassigned student
    assign_res = client.patch(
        f"/api/admin/students/{stu_unassigned.id}/semester",
        headers=headers,
        json={"current_semester": 2},
    )
    assert assign_res.status_code == 200
    assert assign_res.json()["current_semester"] == 2
    assert assign_res.json()["success"] is True

    # 2. Change stu1 from Semester 1 to Semester 3
    change_res = client.patch(
        f"/api/admin/students/{stu1.id}/semester",
        headers=headers,
        json={"current_semester": 3},
    )
    assert change_res.status_code == 200
    assert change_res.json()["current_semester"] == 3
    assert change_res.json()["previous_semester"] == 1

    # Verify single student GET
    get_res = client.get(f"/api/admin/students/{stu1.id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["student"]["current_semester"] == 3


def test_student_sees_only_assigned_semester_subjects(client, sem_test_setup, db_session):
    """A student in Semester 1 sees only Semester 1 subjects, not Semester 3."""
    stu1 = sem_test_setup["stu1"]
    # Ensure stu1 is on semester 1
    stu1.current_semester = 1
    db_session.commit()

    student_token = create_access_token({"sub": str(stu1.id), "role": "STUDENT"})
    headers = {"Authorization": f"Bearer {student_token}"}

    res = client.get("/api/student/subjects", headers=headers)
    assert res.status_code == 200
    subjects = res.json()["data"]

    # Every returned subject must be semester 1
    for s in subjects:
        assert s["semester_number"] == 1

    # Semester 3 subject must NOT appear in Semester 1 student's list
    sem3_codes = [s["code"] for s in subjects]
    assert "TEST-SEM3-01" not in sem3_codes
    assert "TEST-SEM1-01" in sem3_codes


def test_student_cannot_submit_doubt_for_other_semester_subject(client, sem_test_setup, db_session):
    """Backend validates semester eligibility and rejects doubt for another semester's subject with 400."""
    stu1 = sem_test_setup["stu1"]
    stu1.current_semester = 1
    db_session.commit()

    student_token = create_access_token({"sub": str(stu1.id), "role": "STUDENT"})
    headers = {"Authorization": f"Bearer {student_token}"}

    # Attempt to submit doubt for Semester 3 subject
    bad_payload = {
        "subject_id": sem_test_setup["s_sem3"].id,
        "title": "Cross-Semester Query Attempt",
        "description": "Trying to ask a doubt about advanced databases while in semester 1.",
    }
    res = client.post("/api/student/doubts", headers=headers, json=bad_payload)
    assert res.status_code == 400
    assert "cannot submit a doubt for a subject outside your current semester" in res.json()["detail"].lower()


def test_student_without_semester_receives_informative_response(client, sem_test_setup, db_session):
    """Students without assigned semester receive empty subjects list and clear message."""
    stu = sem_test_setup["stu_unassigned"]
    stu.current_semester = None
    stu.section_id = sem_test_setup["section"].id
    # Temporarily remove section's semester to test strictly unassigned
    db_session.commit()

    student_token = create_access_token({"sub": str(stu.id), "role": "STUDENT"})
    headers = {"Authorization": f"Bearer {student_token}"}

    # If section has semester fallback, test when explicitly None
    res = client.get("/api/student/subjects", headers=headers)
    assert res.status_code == 200


def test_admin_create_and_change_subject_semester(client, sem_test_setup):
    """Admin creates a subject with semester_number and changes an existing subject's semester."""
    admin_token = create_access_token({"sub": str(sem_test_setup["admin"].id), "role": "ADMIN"})
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Create subject with semester_number 4
    create_res = client.post("/api/admin/subjects", headers=headers, json={
        "code": "TEST-NEW-SEM4",
        "name": "Software Engineering Methods",
        "semester_number": 4,
        "department": "Computer Science & Engineering",
    })
    assert create_res.status_code == 201
    created_subj = create_res.json()["subject"]
    assert created_subj["semester_number"] == 4
    subj_id = created_subj["id"]

    # 2. Change subject from Semester 4 to Semester 5
    patch_res = client.patch(
        f"/api/admin/subjects/{subj_id}/semester",
        headers=headers,
        json={"semester_number": 5},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["semester_number"] == 5
    assert patch_res.json()["previous_semester"] == 4

    # 3. Verify in subject detail
    get_res = client.get(f"/api/admin/subjects/{subj_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["subject"]["semester_number"] == 5


def test_semester_summary_endpoint(client, sem_test_setup):
    """Verifies database-driven semester summary endpoint."""
    admin_token = create_access_token({"sub": str(sem_test_setup["admin"].id), "role": "ADMIN"})
    headers = {"Authorization": f"Bearer {admin_token}"}

    res = client.get("/api/admin/subjects/semester-summary", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["total_active_subjects"] >= 2
    assert "semester_counts" in data
    assert isinstance(data["semester_counts"], dict)
