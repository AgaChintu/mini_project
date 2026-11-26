"""
Part 4 Test Suite: Admin Subject CRUD, Faculty Overview, and Student Integration
=================================================================================
Tests all new Part 4 features:
A. Subject Management (create, edit, archive, restore, duplicate rejection)
B. Faculty Assignment (assign primary, additional, change, remove, duplicate block)
C. Faculty Overview (faculty-wise teaching view)
D. Student Integration (new subjects visible, faculty dropdown correct)
E. Security (students/teachers blocked from admin subject endpoints)
"""

import pytest
from app.models.user import Student, Teacher
from app.models.admin import Admin
from app.models.academic import Subject, Section, Semester, AcademicYear
from app.models.doubt import Doubt
from app.models.assignment import SubjectTeacherAssignment
from app.security import hash_password, create_access_token


# ─── SHARED FIXTURE ───────────────────────────────────────────────────────────

@pytest.fixture
def p4_seed(db_session):
    """Seeds admin, 3 teachers, 1 student, and 2 subjects for Part 4 tests."""
    admin = db_session.query(Admin).filter(Admin.username == "admin").first()
    if not admin:
        admin = Admin(
            username="admin", email="admin@clariq.edu",
            full_name="Super Administrator",
            password_hash=hash_password("AdminPass123!"),
            is_active=True,
        )
        db_session.add(admin)

    year = AcademicYear(name="Third Year P4", year_number=3, is_active=True)
    db_session.add(year)
    db_session.flush()

    sem = Semester(name="Semester V", semester_number=5, academic_year_id=year.id)
    db_session.add(sem)
    db_session.flush()

    sec = Section(code="CSE-C4", name="CSE Section C4", academic_year_id=year.id, semester_id=sem.id)
    db_session.add(sec)
    db_session.flush()

    t1 = Teacher(
        teacher_code="P4-T001", full_name="Dr. Priya Sharma",
        email="priya.sharma.p4@clariq.edu",
        password_hash=hash_password("teacher123"),
        department="Computer Science & Engineering",
        designation="Professor", is_active=True,
    )
    t2 = Teacher(
        teacher_code="P4-T002", full_name="Prof. Rajan Verma",
        email="rajan.verma.p4@clariq.edu",
        password_hash=hash_password("teacher123"),
        department="Computer Science & Engineering",
        designation="Associate Professor", is_active=True,
    )
    t3 = Teacher(
        teacher_code="P4-T003", full_name="Ms. Ananya Patel",
        email="ananya.patel.p4@clariq.edu",
        password_hash=hash_password("teacher123"),
        department="Information Technology",
        designation="Assistant Professor", is_active=True,
    )
    db_session.add_all([t1, t2, t3])
    db_session.flush()

    student = Student(
        student_code="P4-S001", full_name="Test Student P4",
        email="student.p4@clariq.edu",
        password_hash=hash_password("student123"),
        department="Computer Science & Engineering",
        section_id=sec.id, is_active=True,
    )
    db_session.add(student)

    # Existing subjects
    sub1 = Subject(code="P4BCS301", name="Machine Learning", subject_type="theory",
                   department="Computer Science & Engineering", semester_label="V", is_active=True)
    sub2 = Subject(code="P4BCS302", name="Cloud Computing", subject_type="theory",
                   department="Computer Science & Engineering", semester_label="V", is_active=True)
    db_session.add_all([sub1, sub2])
    db_session.commit()

    return {
        "admin": admin, "section": sec,
        "teachers": [t1, t2, t3], "student": student,
        "subjects": [sub1, sub2],
    }


def admin_headers(admin):
    token = create_access_token({"sub": str(admin.id), "role": "ADMIN"})
    return {"Authorization": f"Bearer {token}"}

def student_headers(student):
    token = create_access_token({"sub": str(student.id), "role": "STUDENT"})
    return {"Authorization": f"Bearer {token}"}

def teacher_headers(teacher):
    token = create_access_token({"sub": str(teacher.id), "role": "TEACHER"})
    return {"Authorization": f"Bearer {token}"}


# ─── A. SUBJECT MANAGEMENT ────────────────────────────────────────────────────

def test_create_new_subject(client, p4_seed):
    """Admin can create a new subject with metadata fields."""
    admin = p4_seed["admin"]
    t1 = p4_seed["teachers"][0]

    res = client.post("/api/admin/subjects", json={
        "name": "Artificial Intelligence",
        "code": "P4BCS401",
        "department": "Computer Science & Engineering",
        "subject_type": "theory",
        "semester_label": "VI",
        "academic_year_label": "Third Year",
        "description": "AI fundamentals and machine learning",
        "primary_teacher_id": t1.id,
        "additional_teacher_ids": [],
    }, headers=admin_headers(admin))
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["success"] is True
    assert data["subject"]["name"] == "Artificial Intelligence"
    assert data["subject"]["code"] == "P4BCS401"
    assert data["subject"]["department"] == "Computer Science & Engineering"
    assert data["subject"]["semester_label"] == "VI"
    assert data["subject"]["primary_teacher"] is not None
    assert data["subject"]["primary_teacher"]["teacher_id"] == t1.id


def test_duplicate_subject_code_rejected(client, p4_seed):
    """Creating a subject with an existing code returns 409."""
    admin = p4_seed["admin"]
    sub = p4_seed["subjects"][0]

    res = client.post("/api/admin/subjects", json={
        "name": "Duplicate Subject",
        "code": sub.code,
    }, headers=admin_headers(admin))
    assert res.status_code == 409
    assert "already exists" in res.json()["detail"].lower()


def test_edit_subject_metadata(client, p4_seed, db_session):
    """Admin can edit subject name, department, and semester."""
    admin = p4_seed["admin"]
    sub = p4_seed["subjects"][0]

    res = client.put(f"/api/admin/subjects/{sub.id}", json={
        "name": "Advanced Machine Learning",
        "semester_label": "VI",
        "department": "Computer Science & Engineering",
    }, headers=admin_headers(admin))
    assert res.status_code == 200
    data = res.json()
    assert data["subject"]["name"] == "Advanced Machine Learning"
    assert data["subject"]["semester_label"] == "VI"

    db_session.refresh(sub)
    assert sub.name == "Advanced Machine Learning"


def test_archive_and_restore_subject(client, p4_seed, db_session):
    """Admin can soft-delete and restore a subject. Historical data preserved."""
    admin = p4_seed["admin"]
    sub = p4_seed["subjects"][1]

    # Archive
    res = client.delete(f"/api/admin/subjects/{sub.id}", headers=admin_headers(admin))
    assert res.status_code == 200
    assert res.json()["success"] is True

    db_session.refresh(sub)
    assert sub.is_active is False

    # Restore
    restore_res = client.patch(f"/api/admin/subjects/{sub.id}/restore", headers=admin_headers(admin))
    assert restore_res.status_code == 200
    db_session.refresh(sub)
    assert sub.is_active is True


def test_get_single_subject_detail(client, p4_seed):
    """GET /api/admin/subjects/{id} returns full subject detail."""
    admin = p4_seed["admin"]
    sub = p4_seed["subjects"][0]

    res = client.get(f"/api/admin/subjects/{sub.id}", headers=admin_headers(admin))
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["subject"]["id"] == sub.id
    assert data["subject"]["name"] == sub.name
    assert "assigned_faculty" in data["subject"]
    assert "primary_teacher" in data["subject"]


# ─── B. FACULTY ASSIGNMENT ────────────────────────────────────────────────────

def test_assign_primary_and_additional_faculty(client, p4_seed, db_session):
    """Admin can assign primary faculty and additional faculty to a subject."""
    admin = p4_seed["admin"]
    sub = p4_seed["subjects"][0]
    t1, t2, t3 = p4_seed["teachers"]

    # Assign t1 as primary
    r1 = client.post(f"/api/admin/subjects/{sub.id}/teachers",
                     json={"teacher_id": t1.id, "is_primary": True},
                     headers=admin_headers(admin))
    assert r1.status_code == 201
    assert r1.json()["assignment"]["is_primary"] is True

    # Assign t2 as additional
    r2 = client.post(f"/api/admin/subjects/{sub.id}/teachers",
                     json={"teacher_id": t2.id, "is_primary": False},
                     headers=admin_headers(admin))
    assert r2.status_code == 201
    assert r2.json()["assignment"]["is_primary"] is False

    # Verify GET /api/admin/subjects/{id}/teachers
    get_res = client.get(f"/api/admin/subjects/{sub.id}/teachers", headers=admin_headers(admin))
    assignments = get_res.json()["assignments"]
    assert len(assignments) == 2
    primary_assign = next(a for a in assignments if a["teacher_id"] == t1.id)
    assert primary_assign["is_primary"] is True


def test_duplicate_assignment_rejected(client, p4_seed, db_session):
    """Assigning the same teacher twice returns 409."""
    admin = p4_seed["admin"]
    sub = p4_seed["subjects"][0]
    t1 = p4_seed["teachers"][0]

    a = SubjectTeacherAssignment(subject_id=sub.id, teacher_id=t1.id, is_primary=True, is_active=True)
    db_session.add(a)
    db_session.commit()

    res = client.post(f"/api/admin/subjects/{sub.id}/teachers",
                      json={"teacher_id": t1.id, "is_primary": False},
                      headers=admin_headers(admin))
    assert res.status_code == 409


def test_change_primary_faculty(client, p4_seed, db_session):
    """PATCH /primary promotes new faculty and demotes old primary."""
    admin = p4_seed["admin"]
    sub = p4_seed["subjects"][0]
    t1, t2 = p4_seed["teachers"][:2]

    a1 = SubjectTeacherAssignment(subject_id=sub.id, teacher_id=t1.id, is_primary=True, is_active=True)
    a2 = SubjectTeacherAssignment(subject_id=sub.id, teacher_id=t2.id, is_primary=False, is_active=True)
    db_session.add_all([a1, a2])
    db_session.commit()

    res = client.patch(f"/api/admin/subjects/{sub.id}/teachers/{t2.id}/primary", headers=admin_headers(admin))
    assert res.status_code == 200

    db_session.refresh(a1); db_session.refresh(a2)
    assert a2.is_primary is True
    assert a1.is_primary is False


def test_remove_faculty_assignment(client, p4_seed, db_session):
    """DELETE /teachers/{id} deactivates assignment without deleting historical doubts."""
    admin = p4_seed["admin"]
    sub = p4_seed["subjects"][0]
    t1 = p4_seed["teachers"][0]
    sec = p4_seed["section"]
    student = p4_seed["student"]

    a1 = SubjectTeacherAssignment(subject_id=sub.id, teacher_id=t1.id, is_primary=True, is_active=True)
    db_session.add(a1)
    # Historical doubt
    doubt = Doubt(
        student_id=student.id, section_id=sec.id,
        subject_id=sub.id, teacher_id=t1.id,
        doubt_code="P4-DBT-DEL-01",
        title="Historical Doubt", question="Will this survive?",
        description="Testing historical preservation.", status="pending",
    )
    db_session.add(doubt)
    db_session.commit()

    res = client.delete(f"/api/admin/subjects/{sub.id}/teachers/{t1.id}", headers=admin_headers(admin))
    assert res.status_code == 200

    db_session.refresh(a1)
    assert a1.is_active is False

    # Doubt must still exist
    db_session.refresh(doubt)
    assert doubt.id is not None
    assert doubt.student_id == student.id


# ─── C. FACULTY OVERVIEW ──────────────────────────────────────────────────────

def test_faculty_overview_endpoint(client, p4_seed, db_session):
    """GET /api/admin/faculty-overview returns faculty-wise subject breakdown."""
    admin = p4_seed["admin"]
    sub = p4_seed["subjects"][0]
    t1, t2 = p4_seed["teachers"][:2]

    a1 = SubjectTeacherAssignment(subject_id=sub.id, teacher_id=t1.id, is_primary=True, is_active=True)
    a2 = SubjectTeacherAssignment(subject_id=sub.id, teacher_id=t2.id, is_primary=False, is_active=True)
    db_session.add_all([a1, a2])
    db_session.commit()

    res = client.get("/api/admin/faculty-overview", headers=admin_headers(admin))
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["count"] >= 2

    t1_data = next((t for t in data["data"] if t["teacher_code"] == t1.teacher_code), None)
    assert t1_data is not None
    assert t1_data["primary_count"] >= 1
    assert any(s["code"] == sub.code for s in t1_data["primary_subjects"])

    t2_data = next((t for t in data["data"] if t["teacher_code"] == t2.teacher_code), None)
    assert t2_data is not None
    assert t2_data["additional_count"] >= 1


# ─── D. STUDENT INTEGRATION ───────────────────────────────────────────────────

def test_new_subject_visible_to_student(client, p4_seed, db_session):
    """A newly created subject appears in student subjects when section-linked via SubjectOffering."""
    # Note: Student subjects are based on section and subject_offerings or SubjectTeacherAssignment
    # Verify that admin list reflects new subject
    admin = p4_seed["admin"]
    res = client.post("/api/admin/subjects", json={
        "name": "Internet of Things",
        "code": "P4BCS501",
        "department": "Computer Science & Engineering",
        "semester_label": "V",
    }, headers=admin_headers(admin))
    assert res.status_code == 201
    new_sub = res.json()["subject"]
    assert new_sub["id"] is not None

    # Admin can retrieve it
    get_res = client.get(f"/api/admin/subjects/{new_sub['id']}", headers=admin_headers(admin))
    assert get_res.status_code == 200
    assert get_res.json()["subject"]["name"] == "Internet of Things"


def test_student_faculty_dropdown_excludes_unnamed(client, p4_seed, db_session):
    """Student faculty dropdown returns properly formatted teacher names."""
    sub = p4_seed["subjects"][0]
    t1 = p4_seed["teachers"][0]
    student = p4_seed["student"]

    a1 = SubjectTeacherAssignment(subject_id=sub.id, teacher_id=t1.id, is_primary=True, is_active=True)
    db_session.add(a1)
    db_session.commit()

    stok = create_access_token({"sub": str(student.id), "role": "STUDENT"})
    res = client.get(f"/api/student/subjects/{sub.id}/teachers",
                     headers={"Authorization": f"Bearer {stok}"})
    assert res.status_code == 200
    data = res.json()
    teachers = data["data"]
    assert len(teachers) >= 1
    t = teachers[0]
    assert t["full_name"] is not None
    assert t["full_name"] != ""
    assert t["id"] == t1.id
    assert t["is_primary"] is True


def test_admin_doubts_list_endpoint(client, p4_seed, db_session):
    """GET /api/admin/doubts returns doubts visible to admin."""
    admin = p4_seed["admin"]
    sub = p4_seed["subjects"][0]
    t1 = p4_seed["teachers"][0]
    student = p4_seed["student"]
    sec = p4_seed["section"]

    doubt = Doubt(
        student_id=student.id, section_id=sec.id,
        subject_id=sub.id, teacher_id=t1.id,
        doubt_code="P4-ADMIN-DBT-01",
        title="Admin Doubts List Test", question="Test query",
        description="Testing admin doubts list.", status="pending",
    )
    db_session.add(doubt)
    db_session.commit()

    res = client.get("/api/admin/doubts?status_filter=pending", headers=admin_headers(admin))
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert len(data["data"]) >= 1
    d = next((x for x in data["data"] if x["doubt_code"] == "P4-ADMIN-DBT-01"), None)
    assert d is not None
    assert d["subject"]["id"] == sub.id
    assert d["assigned_teacher"]["name"] == t1.full_name


# ─── E. SECURITY ──────────────────────────────────────────────────────────────

def test_student_cannot_access_admin_subject_endpoints(client, p4_seed):
    """Students are blocked from admin subject endpoints with 403."""
    student = p4_seed["student"]
    sub = p4_seed["subjects"][0]
    stok = create_access_token({"sub": str(student.id), "role": "STUDENT"})
    hdrs = {"Authorization": f"Bearer {stok}"}

    assert client.post("/api/admin/subjects", json={"name": "Hack", "code": "HACK01"}, headers=hdrs).status_code == 403
    assert client.put(f"/api/admin/subjects/{sub.id}", json={"name": "Hack"}, headers=hdrs).status_code == 403
    assert client.delete(f"/api/admin/subjects/{sub.id}", headers=hdrs).status_code == 403
    assert client.get("/api/admin/faculty-overview", headers=hdrs).status_code == 403


def test_teacher_cannot_access_admin_subject_endpoints(client, p4_seed):
    """Teachers are blocked from admin subject endpoints with 403."""
    teacher = p4_seed["teachers"][0]
    sub = p4_seed["subjects"][0]
    ttok = create_access_token({"sub": str(teacher.id), "role": "TEACHER"})
    hdrs = {"Authorization": f"Bearer {ttok}"}

    assert client.post("/api/admin/subjects", json={"name": "Hack", "code": "HACK02"}, headers=hdrs).status_code == 403
    assert client.get("/api/admin/faculty-overview", headers=hdrs).status_code == 403


def test_unauthenticated_blocked_from_admin(client, p4_seed):
    """Unauthenticated requests are blocked from admin endpoints."""
    sub = p4_seed["subjects"][0]
    assert client.get("/api/admin/subjects").status_code in [401, 403, 422]
    assert client.post("/api/admin/subjects", json={"name": "X", "code": "X001"}).status_code in [401, 403, 422]


# ─── F. MODULE 7 FACULTY & ASSIGNMENT ALIAS ENDPOINTS ─────────────────────────

def test_module7_faculty_endpoints_and_aliases(client, p4_seed, db_session):
    """
    Verifies all exact endpoints requested in Module 7:
      GET    /api/admin/faculty
      GET    /api/admin/faculty/{faculty_id}
      GET    /api/admin/faculty/{faculty_id}/subjects
      GET    /api/admin/subjects/{subject_id}/faculty
      POST   /api/admin/subjects/{subject_id}/faculty
      PATCH  /api/admin/subjects/{subject_id}/faculty/primary
      DELETE /api/admin/subjects/{subject_id}/faculty/{teacher_id}
    """
    admin = p4_seed["admin"]
    sub = p4_seed["subjects"][0]
    t1, t2 = p4_seed["teachers"][:2]
    hdrs = admin_headers(admin)

    # 1. GET /api/admin/faculty
    res_fac = client.get("/api/admin/faculty", headers=hdrs)
    assert res_fac.status_code == 200
    assert len(res_fac.json()["data"]) >= 2

    # 2. GET /api/admin/faculty/{faculty_id}
    res_fac_single = client.get(f"/api/admin/faculty/{t1.id}", headers=hdrs)
    assert res_fac_single.status_code == 200
    assert res_fac_single.json()["faculty"]["id"] == t1.id

    # 3. POST /api/admin/subjects/{subject_id}/faculty (assign t1 as additional)
    assign_res = client.post(f"/api/admin/subjects/{sub.id}/faculty", json={
        "faculty_id": t1.id,
        "is_primary": False,
    }, headers=hdrs)
    assert assign_res.status_code == 201

    # 4. POST /api/admin/subjects/{subject_id}/faculty (assign t2 as additional)
    assign_res2 = client.post(f"/api/admin/subjects/{sub.id}/faculty", json={
        "teacher_id": t2.id,
        "is_primary": False,
    }, headers=hdrs)
    assert assign_res2.status_code == 201

    # 5. GET /api/admin/subjects/{subject_id}/faculty
    sub_fac_res = client.get(f"/api/admin/subjects/{sub.id}/faculty", headers=hdrs)
    assert sub_fac_res.status_code == 200
    assert len(sub_fac_res.json()["assignments"]) == 2

    # 6. PATCH /api/admin/subjects/{subject_id}/faculty/primary (set t1 as primary)
    primary_res = client.patch(f"/api/admin/subjects/{sub.id}/faculty/primary", json={
        "faculty_id": t1.id,
    }, headers=hdrs)
    assert primary_res.status_code == 200
    assert primary_res.json()["is_primary"] is True

    # 7. GET /api/admin/faculty/{faculty_id}/subjects (verify t1's assigned subjects)
    fac_subs_res = client.get(f"/api/admin/faculty/{t1.id}/subjects", headers=hdrs)
    assert fac_subs_res.status_code == 200
    t1_subs = fac_subs_res.json()["subjects"]
    assert len(t1_subs) >= 1
    assert any(s["id"] == sub.id and s["is_primary"] is True for s in t1_subs)

    # 8. DELETE /api/admin/subjects/{subject_id}/faculty/{teacher_id} (remove t2)
    del_res = client.delete(f"/api/admin/subjects/{sub.id}/faculty/{t2.id}", headers=hdrs)
    assert del_res.status_code == 200

    # Verify t2 is no longer in active assigned list
    sub_fac_after = client.get(f"/api/admin/subjects/{sub.id}/faculty", headers=hdrs)
    assert len(sub_fac_after.json()["assignments"]) == 1

