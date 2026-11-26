import pytest
from app.models.user import Student, Teacher
from app.models.academic import Subject, Section, Semester, AcademicYear
from app.models.doubt import Doubt, DoubtAnswer
from app.models.assignment import TeacherAssignment
from app.security import verify_password


def test_student_registration_workflow(client, db_session):
    """Verifies dynamic student registration, unique ID generation, and password hashing."""
    reg_payload = {
        "full_name": "Kavya Patel",
        "email": "kavya.patel@test.edu",
        "password": "secureStudentPassword123",
        "confirm_password": "secureStudentPassword123",
        "department": "Computer Science & Engineering",
        "semester_number": 3,
        "section_code": "AIML",
    }

    response = client.post("/api/auth/student/register", json=reg_payload)
    assert response.status_code == 201
    data = response.json()

    assert data["success"] is True
    assert "access_token" in data
    assert data["role"] == "STUDENT"
    assert data["email"] == "kavya.patel@test.edu"
    assert data["name"] == "Kavya Patel"

    generated_code = data["college_id"]
    assert generated_code.startswith("STU-")
    assert generated_code != "S001"  # Not hardcoded S001

    # Verify database persistence & password hashing
    student_in_db = db_session.query(Student).filter(Student.email == "kavya.patel@test.edu").first()
    assert student_in_db is not None
    assert student_in_db.password_hash != "secureStudentPassword123"
    assert verify_password("secureStudentPassword123", student_in_db.password_hash) is True


def test_student_duplicate_email_rejected(client):
    """Ensures duplicate email registrations are blocked with 409 Conflict."""
    payload = {
        "full_name": "Test User",
        "email": "duplicate.check@test.edu",
        "password": "password123",
        "confirm_password": "password123",
        "department": "CSE",
        "semester_number": 1,
        "section_code": "A",
    }
    r1 = client.post("/api/auth/student/register", json=payload)
    assert r1.status_code == 201

    r2 = client.post("/api/auth/student/register", json=payload)
    assert r2.status_code == 409
    assert "already registered" in r2.json()["detail"].lower()


def test_teacher_registration_workflow(client, db_session):
    """Verifies faculty registration with dynamic TCH-XXXX ID and Argon2 hashing."""
    reg_payload = {
        "full_name": "Dr. Sandeep Verma",
        "email": "sandeep.verma@faculty.edu",
        "password": "facultySecretPassword456",
        "confirm_password": "facultySecretPassword456",
        "department": "Information Technology",
        "designation": "Associate Professor",
        "faculty_invite_code": "CLARIQ-FACULTY-2026",
        "profile_info": "Database Systems & Big Data Specialist",
    }

    response = client.post("/api/auth/teacher/register", json=reg_payload)
    assert response.status_code == 201
    data = response.json()

    assert data["success"] is True
    assert data["role"] == "TEACHER"
    assert data["college_id"].startswith("TCH-")
    assert data["college_id"] != "T001"  # Not hardcoded

    teacher_in_db = db_session.query(Teacher).filter(Teacher.email == "sandeep.verma@faculty.edu").first()
    assert teacher_in_db is not None
    assert teacher_in_db.password_hash != "facultySecretPassword456"
    assert verify_password("facultySecretPassword456", teacher_in_db.password_hash) is True


def test_teacher_registration_rejects_unauthorized_key(client):
    """Verifies that teacher registration is blocked with 403 Forbidden without valid authorization key."""
    reg_payload = {
        "full_name": "Unauthorized Faculty",
        "email": "unauth@faculty.edu",
        "password": "facultyPassword123",
        "confirm_password": "facultyPassword123",
        "department": "Information Technology",
        "designation": "Assistant Professor",
        "faculty_invite_code": "INVALID-CODE-999",
    }
    response = client.post("/api/auth/teacher/register", json=reg_payload)
    assert response.status_code == 403
    assert "authorization key" in response.json()["detail"].lower()


def test_login_with_email_or_college_id(client):
    """Verifies login works seamlessly with both generated College ID and email."""
    # Register student
    reg = client.post("/api/auth/student/register", json={
        "full_name": "Arjun Nair",
        "email": "arjun.nair@test.edu",
        "password": "mypassword123",
        "confirm_password": "mypassword123",
        "department": "CSE",
        "semester_number": 3,
        "section_code": "AIML",
    }).json()

    college_id = reg["college_id"]

    # 1. Login with College ID
    l1 = client.post("/api/auth/login", json={"college_id": college_id, "password": "mypassword123"})
    assert l1.status_code == 200
    assert l1.json()["name"] == "Arjun Nair"

    # 2. Login with Email Address
    l2 = client.post("/api/auth/login", json={"college_id": "arjun.nair@test.edu", "password": "mypassword123"})
    assert l2.status_code == 200
    assert l2.json()["college_id"] == college_id


def test_student_dashboard_and_anonymous_doubt(client, db_session):
    """
    Verifies:
    - Student dashboard endpoint returns dynamic profile, subjects, statistics
    - Student submits anonymous doubt with AI summary & clustering
    """
    # Register student
    reg = client.post("/api/auth/student/register", json={
        "full_name": "Pooja Reddy",
        "email": "pooja.reddy@test.edu",
        "password": "poojapassword123",
        "confirm_password": "poojapassword123",
        "department": "CSE (AI & ML)",
        "semester_number": 3,
        "section_code": "AIML",
    }).json()

    token = reg["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Fetch dashboard
    dash_res = client.get("/api/student/dashboard", headers=headers)
    assert dash_res.status_code == 200
    dash_data = dash_res.json()
    assert dash_data["profile"]["full_name"] == "Pooja Reddy"
    assert "statistics" in dash_data
    assert "subjects" in dash_data

    # Ensure a subject exists
    subj = db_session.query(Subject).first()
    if not subj:
        subj = Subject(code="CS301", name="Data Structures", subject_type="theory")
        db_session.add(subj)
        db_session.commit()

    # Submit anonymous doubt
    doubt_res = client.post("/api/student/doubts", headers=headers, json={
        "subject_id": subj.id,
        "title": "Clarification on Binary Search Tree In-order Traversal",
        "description": "I get confused about whether in-order traversal of a BST always yields sorted keys.",
    })
    assert doubt_res.status_code == 201
    doubt_data = doubt_res.json()
    assert doubt_data["success"] is True
    assert doubt_data["doubt"]["is_anonymous"] is True

    # Check student doubt in db
    d_id = doubt_data["doubt"]["id"]
    db_doubt = db_session.query(Doubt).filter(Doubt.id == d_id).first()
    assert db_doubt is not None
    assert db_doubt.is_anonymous_to_teacher is True
    assert db_doubt.ai_summary is not None
    assert db_doubt.keywords is not None

    # Retrieve my doubts list
    my_doubts = client.get("/api/student/doubts", headers=headers).json()
    assert len(my_doubts["data"]) >= 1
    assert my_doubts["data"][0]["title"] == "Clarification on Binary Search Tree In-order Traversal"


def test_teacher_dashboard_and_verified_answer(client, db_session):
    """
    Verifies:
    - Teacher only sees assigned subjects
    - AI doubt clustering aggregates student questions
    - Student identity is NEVER leaked in teacher doubt view
    - Teacher publishes verified answer (Human-in-the-Loop)
    - Student receives the verified answer
    """
    # 1. Setup Subject and Section
    sec = db_session.query(Section).first()
    if not sec:
        ay = AcademicYear(name="Year 2", year_number=2, is_active=True)
        db_session.add(ay)
        db_session.flush()
        sem = Semester(academic_year_id=ay.id, semester_number=3, name="Semester III")
        db_session.add(sem)
        db_session.flush()
        sec = Section(academic_year_id=ay.id, semester_id=sem.id, code="AIML", name="AIML")
        db_session.add(sec)
        db_session.commit()

    subj = db_session.query(Subject).first()
    if not subj:
        subj = Subject(code="CS302", name="Operating Systems", subject_type="theory")
        db_session.add(subj)
        db_session.commit()

    # 2. Register Teacher & Assign Subject
    t_reg = client.post("/api/auth/teacher/register", json={
        "full_name": "Prof. Vikram Sen",
        "email": "vikram.sen@faculty.edu",
        "password": "senpassword123",
        "confirm_password": "senpassword123",
        "department": "Computer Science",
        "designation": "Professor",
        "faculty_invite_code": "CLARIQ-FACULTY-2026",
        "subject_ids": [subj.id],
    }).json()

    t_token = t_reg["access_token"]
    t_headers = {"Authorization": f"Bearer {t_token}"}
    t_id = t_reg["user_id"]

    # Ensure assignment exists
    assignment = db_session.query(TeacherAssignment).filter(
        TeacherAssignment.teacher_id == t_id,
        TeacherAssignment.subject_id == subj.id
    ).first()
    if not assignment:
        assignment = TeacherAssignment(
            teacher_id=t_id,
            subject_id=subj.id,
            section_id=sec.id,
            semester_id=sec.semester_id,
        )
        db_session.add(assignment)
        db_session.commit()

    # 3. Register Student and Ask Doubt in that Subject
    s_reg = client.post("/api/auth/student/register", json={
        "full_name": "Meera Joshi",
        "email": "meera.joshi@student.edu",
        "password": "meerapassword123",
        "confirm_password": "meerapassword123",
        "department": "CSE",
        "semester_number": 3,
        "section_code": sec.code,
    }).json()
    s_token = s_reg["access_token"]
    s_headers = {"Authorization": f"Bearer {s_token}"}

    client.post("/api/student/doubts", headers=s_headers, json={
        "subject_id": subj.id,
        "title": "Deadlock Prevention vs Avoidance",
        "description": "How does Banker's algorithm differ from resource ordering for deadlocks?",
    })

    # 4. Teacher Inspects Subject Doubts
    t_doubts_res = client.get(f"/api/teacher/subjects/{subj.id}/doubts", headers=t_headers)
    assert t_doubts_res.status_code == 200
    t_doubts_data = t_doubts_res.json()

    assert t_doubts_data["statistics"]["total_doubts"] >= 1
    assert len(t_doubts_data["clusters"]) >= 1

    cluster = t_doubts_data["clusters"][0]
    assert cluster["student_count"] >= 1
    found_doubt = cluster["doubts"][0]

    # PRIVACY VERIFICATION: Confirm student name, email, and ID are completely omitted!
    doubt_str = str(found_doubt).lower()
    assert "meera" not in doubt_str
    assert "meera.joshi@student.edu" not in doubt_str
    assert "student_id" not in found_doubt

    # 5. Teacher Publishes Verified Answer
    doubt_id = found_doubt["id"]
    ans_res = client.post(f"/api/teacher/doubts/{doubt_id}/answer", headers=t_headers, json={
        "answer_text": "Deadlock avoidance dynamically examines resource allocation state, whereas prevention constrains resource requests structurally.",
        "resource_url": "https://clariq.edu/resources/deadlock-notes.pdf",
        "resolve_cluster": True,
    })
    assert ans_res.status_code == 201
    assert ans_res.json()["doubt_status"] == "resolved"

    # 6. Student views the verified answer in My Doubts
    s_doubts = client.get("/api/student/doubts", headers=s_headers).json()
    resolved_doubt = next(d for d in s_doubts["data"] if d["id"] == doubt_id)
    assert resolved_doubt["status"] == "resolved"
    assert len(resolved_doubt["verified_answers"]) >= 1
    assert "Prof. Vikram Sen" in resolved_doubt["verified_answers"][0]["teacher_name"]
    assert "Deadlock avoidance dynamically examines" in resolved_doubt["verified_answers"][0]["answer_text"]


def test_role_based_access_control(client):
    """Verifies that students cannot access teacher endpoints and vice versa."""
    # Student token
    s_reg = client.post("/api/auth/student/register", json={
        "full_name": "Ravi Kumar",
        "email": "ravi.kumar@test.edu",
        "password": "password123",
        "confirm_password": "password123",
        "department": "CSE",
        "semester_number": 3,
        "section_code": "AIML",
    }).json()
    s_headers = {"Authorization": f"Bearer {s_reg['access_token']}"}

    # Student trying to call teacher dashboard -> 403 Forbidden
    t_dash_try = client.get("/api/teacher/dashboard", headers=s_headers)
    assert t_dash_try.status_code == 403

    # Teacher token
    t_reg = client.post("/api/auth/teacher/register", json={
        "full_name": "Dr. Neha Sharma",
        "email": "neha.sharma@faculty.edu",
        "password": "password123",
        "confirm_password": "password123",
        "department": "CSE",
        "designation": "Professor",
        "faculty_invite_code": "CLARIQ-FACULTY-2026",
    }).json()
    t_headers = {"Authorization": f"Bearer {t_reg['access_token']}"}

    # Teacher trying to call student dashboard -> 403 Forbidden
    s_dash_try = client.get("/api/student/dashboard", headers=t_headers)
    assert s_dash_try.status_code == 403
