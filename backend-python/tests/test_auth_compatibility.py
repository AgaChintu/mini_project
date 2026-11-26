from app.models.user import Student, Teacher
from app.models.academic import Section, AcademicYear, Semester
from app.security import hash_password


def test_auth_login_and_me_endpoints(client, db_session):
    # Setup test section and student
    year = AcademicYear(name="Auth Test Year", year_number=888)
    db_session.add(year)
    db_session.flush()

    sem = Semester(academic_year_id=year.id, semester_number=1, name="Sem 1")
    db_session.add(sem)
    db_session.flush()

    sec = Section(academic_year_id=year.id, semester_id=sem.id, code="SEC-A", name="Section A")
    db_session.add(sec)
    db_session.flush()

    hashed_pw = hash_password("secret123")
    student = Student(
        student_code="S_AUTH_01",
        full_name="Auth Student",
        email="sauth@clariq.local",
        password_hash=hashed_pw,
        section_id=sec.id,
        is_active=True,
    )
    db_session.add(student)
    db_session.commit()

    # 1. Login with student credentials
    login_res = client.post(
        "/api/auth/login",
        json={"college_id": "S_AUTH_01", "password": "secret123"},
    )
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    token_data = login_res.json()
    assert "access_token" in token_data
    assert token_data["role"] == "STUDENT"
    assert token_data["college_id"] == "S_AUTH_01"

    # 2. Access /api/auth/me with Bearer token
    token = token_data["access_token"]
    me_res = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["college_id"] == "S_AUTH_01"
    assert me_data["role"] == "STUDENT"


def test_auth_login_invalid_credentials(client, db_session):
    res = client.post(
        "/api/auth/login",
        json={"college_id": "NON_EXISTENT", "password": "wrongpassword"},
    )
    assert res.status_code == 401
