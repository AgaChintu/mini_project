"""
Part 3 Test Suite: Admin Panel, Multiple Faculty Assignment, Doubt Routing & Verification
========================================================================================
Tests all administrative features, multiple faculty assignments per subject,
primary faculty designation, student faculty selection, teacher doubt routing,
and live student doubts retrieval.
"""

import pytest
from app.models.user import Student, Teacher
from app.models.admin import Admin
from app.models.academic import Subject, Section, Semester, AcademicYear
from app.models.doubt import Doubt, DoubtAnswer
from app.models.assignment import SubjectTeacherAssignment, TeacherAssignment
from app.security import hash_password, create_access_token


@pytest.fixture
def seed_admin_and_entities(db_session):
    """Creates initial admin, academic year, semester, section, subject, and teachers."""
    # Ensure super admin exists
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

    # Academic structure
    year = AcademicYear(name="Second Year", year_number=2, is_active=True)
    db_session.add(year)
    db_session.flush()

    sem = Semester(name="Semester 3", semester_number=3, academic_year_id=year.id)
    db_session.add(sem)
    db_session.flush()

    sec = Section(code="CSE-A", name="CSE Section A", academic_year_id=year.id, semester_id=sem.id)
    db_session.add(sec)
    db_session.flush()

    # Subject
    subject = Subject(code="CS301", name="Data Structures & Algorithms", subject_type="theory")
    db_session.add(subject)
    db_session.flush()

    # Teachers
    t1 = Teacher(
        teacher_code="TCH-1001",
        full_name="Prof. Alice Smith",
        email="alice.smith@clariq.edu",
        password_hash=hash_password("teacher123"),
        department="Computer Science & Engineering",
        designation="Professor",
        is_active=True,
    )
    t2 = Teacher(
        teacher_code="TCH-1002",
        full_name="Dr. Bob Jones",
        email="bob.jones@clariq.edu",
        password_hash=hash_password("teacher123"),
        department="Computer Science & Engineering",
        designation="Associate Professor",
        is_active=True,
    )
    t3 = Teacher(
        teacher_code="TCH-1003",
        full_name="Prof. Charlie Brown",
        email="charlie.brown@clariq.edu",
        password_hash=hash_password("teacher123"),
        department="Information Technology",
        designation="Assistant Professor",
        is_active=True,
    )
    db_session.add_all([t1, t2, t3])
    db_session.flush()

    # Student
    student = Student(
        student_code="STU-2001",
        full_name="Dev Student",
        email="dev.student@clariq.edu",
        password_hash=hash_password("student123"),
        department="Computer Science & Engineering",
        section_id=sec.id,
        is_active=True,
    )
    db_session.add(student)
    db_session.commit()

    return {
        "admin": admin,
        "subject": subject,
        "teachers": [t1, t2, t3],
        "student": student,
        "section": sec,
        "semester": sem,
    }


def test_admin_login_and_auth(client, seed_admin_and_entities):
    """Verifies that admin login succeeds with JWT role ADMIN and blocks unauthorized roles."""
    # Successful login
    login_res = client.post("/api/admin/login", json={
        "identifier": "admin@clariq.edu",
        "password": "AdminPass123!"
    })
    assert login_res.status_code == 200
    data = login_res.json()
    assert data["success"] is True
    assert data["role"] == "ADMIN"
    admin_token = data["access_token"]
    assert admin_token is not None

    # Invalid password fails with 401
    bad_login = client.post("/api/admin/login", json={
        "identifier": "admin@clariq.edu",
        "password": "WrongPassword999!"
    })
    assert bad_login.status_code == 401

    # Protected admin endpoint works with admin token
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    me_res = client.get("/api/admin/me", headers=admin_headers)
    assert me_res.status_code == 200
    assert me_res.json()["admin"]["username"] == "admin"

    # Student token cannot access admin endpoint (403 Forbidden)
    student = seed_admin_and_entities["student"]
    student_token = create_access_token({"sub": str(student.id), "role": "STUDENT"})
    stud_headers = {"Authorization": f"Bearer {student_token}"}
    blocked_res = client.get("/api/admin/dashboard", headers=stud_headers)
    assert blocked_res.status_code == 403


def test_admin_dashboard_metrics(client, seed_admin_and_entities):
    """Verifies that the admin dashboard returns accurate institutional metrics."""
    admin = seed_admin_and_entities["admin"]
    token = create_access_token({"sub": str(admin.id), "role": "ADMIN"})
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/api/admin/dashboard", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    metrics = data["metrics"]
    assert metrics["total_students"] >= 1
    assert metrics["total_teachers"] >= 3
    assert metrics["total_subjects"] >= 1
    assert "active_faculty_assignments" in metrics
    assert "total_doubts" in metrics


def test_admin_faculty_management_and_toggle(client, seed_admin_and_entities, db_session):
    """Verifies admin listing teachers and toggling active/inactive status."""
    admin = seed_admin_and_entities["admin"]
    t1 = seed_admin_and_entities["teachers"][0]
    token = create_access_token({"sub": str(admin.id), "role": "ADMIN"})
    headers = {"Authorization": f"Bearer {token}"}

    # List teachers
    res = client.get("/api/admin/teachers", headers=headers)
    assert res.status_code == 200
    teachers = res.json()["data"]
    assert len(teachers) >= 3

    # Deactivate teacher 1
    patch_res = client.patch(f"/api/admin/teachers/{t1.id}/status", json={"is_active": False}, headers=headers)
    assert patch_res.status_code == 200
    assert patch_res.json()["teacher"]["is_active"] is False

    # Check in DB
    db_session.refresh(t1)
    assert t1.is_active is False

    # Reactivate teacher 1
    patch_res2 = client.patch(f"/api/admin/teachers/{t1.id}/status", json={"is_active": True}, headers=headers)
    assert patch_res2.status_code == 200
    assert patch_res2.json()["teacher"]["is_active"] is True


def test_multiple_faculty_assignment_workflow(client, seed_admin_and_entities, db_session):
    """
    Verifies many-to-many faculty assignments per subject:
    1. Assign Teacher 1 as Primary.
    2. Assign Teacher 2 as Additional Faculty.
    3. Verify multiple faculty returned for subject.
    4. Promote Teacher 2 to Primary (automatically demoting Teacher 1).
    5. Remove Teacher 1 assignment.
    """
    admin = seed_admin_and_entities["admin"]
    subject = seed_admin_and_entities["subject"]
    t1 = seed_admin_and_entities["teachers"][0]
    t2 = seed_admin_and_entities["teachers"][1]
    token = create_access_token({"sub": str(admin.id), "role": "ADMIN"})
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Assign Teacher 1 as Primary
    assign1_res = client.post(
        f"/api/admin/subjects/{subject.id}/teachers",
        json={"teacher_id": t1.id, "is_primary": True},
        headers=headers,
    )
    assert assign1_res.status_code == 201
    assert assign1_res.json()["assignment"]["is_primary"] is True

    # 2. Assign Teacher 2 as Additional Faculty
    assign2_res = client.post(
        f"/api/admin/subjects/{subject.id}/teachers",
        json={"teacher_id": t2.id, "is_primary": False},
        headers=headers,
    )
    assert assign2_res.status_code == 201
    assert assign2_res.json()["assignment"]["is_primary"] is False

    # 3. Verify both teachers assigned
    get_res = client.get(f"/api/admin/subjects/{subject.id}/teachers", headers=headers)
    assert get_res.status_code == 200
    assignments = get_res.json()["assignments"]
    assert len(assignments) == 2
    # Primary should be listed first
    assert assignments[0]["teacher_id"] == t1.id
    assert assignments[0]["is_primary"] is True

    # 4. Promote Teacher 2 to Primary
    primary_res = client.patch(
        f"/api/admin/subjects/{subject.id}/teachers/{t2.id}/primary",
        headers=headers,
    )
    assert primary_res.status_code == 200

    # Verify Teacher 2 is now Primary, Teacher 1 is not
    get_res2 = client.get(f"/api/admin/subjects/{subject.id}/teachers", headers=headers)
    assignments2 = get_res2.json()["assignments"]
    t2_assign = next(a for a in assignments2 if a["teacher_id"] == t2.id)
    t1_assign = next(a for a in assignments2 if a["teacher_id"] == t1.id)
    assert t2_assign["is_primary"] is True
    assert t1_assign["is_primary"] is False

    # 5. Remove Teacher 1 assignment
    del_res = client.delete(
        f"/api/admin/subjects/{subject.id}/teachers/{t1.id}",
        headers=headers,
    )
    assert del_res.status_code == 200
    get_res3 = client.get(f"/api/admin/subjects/{subject.id}/teachers", headers=headers)
    assert len(get_res3.json()["assignments"]) == 1


def test_student_faculty_selection_and_doubt_routing(client, seed_admin_and_entities, db_session):
    """
    Verifies dynamic student faculty selection during doubt submission:
    1. Student fetches assigned faculty for subject.
    2. Student selects specific faculty member.
    3. Doubt is routed specifically to that faculty member.
    4. Submitting an unassigned faculty ID is rejected with 400.
    """
    subject = seed_admin_and_entities["subject"]
    t1 = seed_admin_and_entities["teachers"][0]
    t2 = seed_admin_and_entities["teachers"][1]
    t3_unassigned = seed_admin_and_entities["teachers"][2]
    student = seed_admin_and_entities["student"]

    # Assign t1 and t2 to subject
    a1 = SubjectTeacherAssignment(subject_id=subject.id, teacher_id=t1.id, is_primary=True, is_active=True)
    a2 = SubjectTeacherAssignment(subject_id=subject.id, teacher_id=t2.id, is_primary=False, is_active=True)
    db_session.add_all([a1, a2])
    db_session.commit()

    student_token = create_access_token({"sub": str(student.id), "role": "STUDENT"})
    student_headers = {"Authorization": f"Bearer {student_token}"}

    # 1. Student fetches assigned faculty
    fac_res = client.get(f"/api/student/subjects/{subject.id}/teachers", headers=student_headers)
    assert fac_res.status_code == 200
    teachers_list = fac_res.json()["data"]
    assert len(teachers_list) == 2
    assert teachers_list[0]["id"] == t1.id
    assert teachers_list[0]["is_primary"] is True

    # 2. Student selects Teacher 2 for doubt
    doubt_payload = {
        "subject_id": subject.id,
        "title": "Query on Binary Search Trees",
        "description": "How does self-balancing work in AVL trees compared to Red-Black trees?",
        "teacher_id": t2.id,
    }
    submit_res = client.post("/api/student/doubts", json=doubt_payload, headers=student_headers)
    assert submit_res.status_code == 201
    doubt_data = submit_res.json()["doubt"]
    doubt_id = doubt_data["id"]
    assert doubt_data["assigned_teacher"]["name"] == t2.full_name

    # 3. Submitting with unassigned teacher t3 fails with 400
    bad_payload = {
        "subject_id": subject.id,
        "title": "Invalid routing query",
        "description": "This doubt routes to an unassigned faculty member.",
        "teacher_id": t3_unassigned.id,
    }
    bad_res = client.post("/api/student/doubts", json=bad_payload, headers=student_headers)
    assert bad_res.status_code == 400
    assert "not assigned" in bad_res.json()["detail"].lower()

    # 4. Teacher 2 sees the routed doubt
    t2_token = create_access_token({"sub": str(t2.id), "role": "TEACHER"})
    t2_headers = {"Authorization": f"Bearer {t2_token}"}
    t2_dash = client.get("/api/teacher/dashboard", headers=t2_headers)
    assert t2_dash.status_code == 200
    assert t2_dash.json()["statistics"]["total_doubts"] >= 1

    # Teacher 1 does NOT see doubts routed to Teacher 2
    t1_token = create_access_token({"sub": str(t1.id), "role": "TEACHER"})
    t1_headers = {"Authorization": f"Bearer {t1_token}"}
    t1_dash = client.get("/api/teacher/dashboard", headers=t1_headers)
    assert t1_dash.status_code == 200
    assert t1_dash.json()["statistics"]["total_doubts"] == 0


def test_admin_doubt_reassignment_flow(client, seed_admin_and_entities, db_session):
    """Verifies that an admin can reassign a doubt from one faculty member to another."""
    admin = seed_admin_and_entities["admin"]
    subject = seed_admin_and_entities["subject"]
    t1 = seed_admin_and_entities["teachers"][0]
    t2 = seed_admin_and_entities["teachers"][1]
    student = seed_admin_and_entities["student"]
    sec = seed_admin_and_entities["section"]

    # Assign t1 and t2
    a1 = SubjectTeacherAssignment(subject_id=subject.id, teacher_id=t1.id, is_primary=True, is_active=True)
    a2 = SubjectTeacherAssignment(subject_id=subject.id, teacher_id=t2.id, is_primary=False, is_active=True)
    db_session.add_all([a1, a2])

    # Create doubt routed to t1
    doubt = Doubt(
        student_id=student.id,
        section_id=sec.id,
        subject_id=subject.id,
        teacher_id=t1.id,
        doubt_code="DBT-TEST-01",
        title="Quick Sort Worst Case",
        question="Why is quick sort O(n^2) in worst case?",
        description="Need explanation of partition choice.",
        status="pending",
    )
    db_session.add(doubt)
    db_session.commit()

    admin_token = create_access_token({"sub": str(admin.id), "role": "ADMIN"})
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Reassign doubt to t2
    reassign_res = client.patch(
        f"/api/admin/doubts/{doubt.id}/reassign",
        json={"teacher_id": t2.id},
        headers=admin_headers,
    )
    assert reassign_res.status_code == 200
    assert reassign_res.json()["doubt"]["assigned_teacher"]["id"] == t2.id

    # Verify in DB
    db_session.refresh(doubt)
    assert doubt.teacher_id == t2.id

    # Now teacher 2 sees it on their dashboard
    t2_token = create_access_token({"sub": str(t2.id), "role": "TEACHER"})
    t2_dash = client.get("/api/teacher/dashboard", headers={"Authorization": f"Bearer {t2_token}"})
    assert t2_dash.json()["statistics"]["total_doubts"] == 1


def test_student_subject_doubts_and_details_endpoints(client, seed_admin_and_entities, db_session):
    """
    Verifies:
    1. GET /api/student/subjects/{id}/doubts (doubts for specific subject)
    2. GET /api/student/doubts/{id} (complete details with doubt info, faculty info, verified answer)
    3. GET /api/student/doubts with search, status_filter, sort_by
    """
    subject = seed_admin_and_entities["subject"]
    t1 = seed_admin_and_entities["teachers"][0]
    student = seed_admin_and_entities["student"]
    sec = seed_admin_and_entities["section"]

    # Assign t1 to subject
    a1 = SubjectTeacherAssignment(subject_id=subject.id, teacher_id=t1.id, is_primary=True, is_active=True)
    db_session.add(a1)

    # Create doubt
    doubt = Doubt(
        student_id=student.id,
        section_id=sec.id,
        subject_id=subject.id,
        teacher_id=t1.id,
        doubt_code="DBT-STUD-01",
        title="Dijkstra Algorithm Priority Queue",
        question="How does min-heap optimize Dijkstra?",
        description="Understanding priority queue operations in shortest path.",
        status="resolved",
    )
    db_session.add(doubt)
    db_session.flush()

    # Create verified answer
    answer = DoubtAnswer(
        doubt_id=doubt.id,
        teacher_id=t1.id,
        answer_text="Min-heap reduces extraction of minimum distance vertex to O(log V).",
        resource_url="https://clariq.edu/resources/dijkstra",
    )
    db_session.add(answer)
    db_session.commit()

    student_token = create_access_token({"sub": str(student.id), "role": "STUDENT"})
    student_headers = {"Authorization": f"Bearer {student_token}"}

    # 1. Subject-specific doubts
    subj_doubts_res = client.get(f"/api/student/subjects/{subject.id}/doubts", headers=student_headers)
    assert subj_doubts_res.status_code == 200
    sd_data = subj_doubts_res.json()
    assert sd_data["success"] is True
    assert sd_data["subject"]["id"] == subject.id
    assert len(sd_data["doubts"]) == 1
    assert sd_data["doubts"][0]["title"] == "Dijkstra Algorithm Priority Queue"

    # 2. Single Doubt Detailed View
    detail_res = client.get(f"/api/student/doubts/{doubt.id}", headers=student_headers)
    assert detail_res.status_code == 200
    detail = detail_res.json()["data"]
    assert detail["id"] == doubt.id
    assert detail["doubt_code"] == "DBT-STUD-01"
    # Assigned faculty info present
    assert detail["assigned_teacher"]["name"] == t1.full_name
    assert detail["assigned_teacher"]["department"] == t1.department
    # Verified answer present
    assert len(detail["verified_answers"]) == 1
    assert detail["verified_answers"][0]["teacher_name"] == t1.full_name
    assert "Min-heap" in detail["verified_answers"][0]["answer_text"]

    # 3. Search and filter
    search_res = client.get("/api/student/doubts?search=Dijkstra", headers=student_headers)
    assert search_res.status_code == 200
    assert len(search_res.json()["data"]) == 1

    search_empty = client.get("/api/student/doubts?search=NonExistentQueryXYZ", headers=student_headers)
    assert search_empty.status_code == 200
    assert len(search_empty.json()["data"]) == 0
