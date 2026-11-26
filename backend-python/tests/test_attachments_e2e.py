import io
from app.models.academic import AcademicYear, Semester, Section, Subject
from app.models.user import Teacher
from app.models.assignment import SubjectTeacherAssignment
from app.security import hash_password
from app.services.storage import storage_service


def test_student_and_teacher_attachments_end_to_end(client, db_session, tmp_path):
    """
    Verifies end-to-end attachment workflow:
    1. Student submits a doubt with an image/PDF attachment via multipart/form-data.
    2. Teacher sees the student's attachment in clustered subject doubts & detail view.
    3. Teacher downloads the student's attachment via teacher attachment endpoint.
    4. Teacher publishes a verified answer with a PDF solution attachment.
    5. Student sees both their attachment and the teacher's solution file in My Doubts,
       and can download both files.
    """
    orig_base_dir = storage_service.base_dir
    storage_service.base_dir = tmp_path
    try:
        ay = AcademicYear(name="Second Year ATT", year_number=99, is_active=True)
        db_session.add(ay)
        db_session.flush()

        sem = Semester(academic_year_id=ay.id, semester_number=3, name="Semester III")
        db_session.add(sem)
        db_session.flush()

        sec = Section(academic_year_id=ay.id, semester_id=sem.id, code="ATT-A", name="Section ATT-A")
        db_session.add(sec)
        db_session.flush()

        subj = Subject(code="ATT101", name="Attachment Engineering", semester_number=3, is_active=True)
        db_session.add(subj)
        db_session.flush()

        teacher = Teacher(
            teacher_code="T_ATT_01",
            full_name="Dr. Attachment Faculty",
            email="att.teacher@clariq.edu",
            password_hash=hash_password("TeacherPass123!"),
            department="CSE",
            designation="Professor",
            is_active=True,
        )
        db_session.add(teacher)
        db_session.flush()

        db_session.add(SubjectTeacherAssignment(
            subject_id=subj.id,
            teacher_id=teacher.id,
            is_primary=True,
            is_active=True,
        ))
        db_session.commit()

        # Register student in Semester 3
        s_reg = client.post("/api/auth/student/register", json={
            "full_name": "Anu Attachment",
            "email": "anu.att@student.edu",
            "password": "StudentPass123!",
            "confirm_password": "StudentPass123!",
            "department": "CSE",
            "semester_number": 3,
            "section_code": sec.code,
        })
        assert s_reg.status_code in (200, 201), s_reg.text
        s_headers = {"Authorization": f"Bearer {s_reg.json()['access_token']}"}

        # Login teacher
        t_login = client.post("/api/auth/login", json={
            "college_id": "att.teacher@clariq.edu",
            "password": "TeacherPass123!",
        })
        assert t_login.status_code == 200, t_login.text
        t_headers = {"Authorization": f"Bearer {t_login.json()['access_token']}"}

        # 1. Student rejects unsupported attachment type
        bad_res = client.post(
            "/api/student/doubts",
            headers=s_headers,
            data={
                "subject_id": str(subj.id),
                "title": "Bad attachment test",
                "description": "Trying to upload an executable file here.",
            },
            files=[("files", ("malware.exe", io.BytesIO(b"MZ"), "application/x-msdownload"))],
        )
        assert bad_res.status_code == 400

        # 2. Student submits doubt with valid PNG image attachment
        student_img_bytes = b"\x89PNG\r\n\x1a\nFakeImageContentForTest"
        submit_res = client.post(
            "/api/student/doubts",
            headers=s_headers,
            data={
                "subject_id": str(subj.id),
                "title": "Diagram clarification needed",
                "description": "Could you explain the memory layout shown in the attached diagram?",
            },
            files=[("files", ("diagram.png", io.BytesIO(student_img_bytes), "image/png"))],
        )
        assert submit_res.status_code == 201, submit_res.text
        doubt_id = submit_res.json()["doubt"]["id"]
        assert submit_res.json()["doubt"]["attachment_count"] == 1

        # 3. Teacher inspects clustered doubts and sees attachment metadata
        t_doubts = client.get(f"/api/teacher/subjects/{subj.id}/doubts", headers=t_headers)
        assert t_doubts.status_code == 200
        clusters = t_doubts.json()["clusters"]
        assert len(clusters) == 1
        found_doubt = clusters[0]["doubts"][0]
        assert len(found_doubt["attachments"]) == 1
        att_id = found_doubt["attachments"][0]["id"]
        assert found_doubt["attachments"][0]["original_filename"] == "diagram.png"

        # 4. Teacher downloads student's attachment
        t_dl = client.get(f"/api/teacher/doubts/{doubt_id}/attachments/{att_id}", headers=t_headers)
        assert t_dl.status_code == 200
        assert t_dl.content == student_img_bytes

        # 5. Teacher rejects unsupported solution file MIME
        bad_sol = client.post(
            f"/api/teacher/doubts/{doubt_id}/answer",
            headers=t_headers,
            data={"answer_text": "Here is the answer text.", "resolve_cluster": "true"},
            files={"solution_file": ("script.sh", io.BytesIO(b"#!/bin/sh"), "text/plain")},
        )
        assert bad_sol.status_code == 400

        # 6. Teacher publishes verified answer with PDF solution file
        teacher_pdf_bytes = b"%PDF-1.4\n%FakeSolutionPDF\n"
        ans_res = client.post(
            f"/api/teacher/doubts/{doubt_id}/answer",
            headers=t_headers,
            data={
                "answer_text": "See the attached annotated PDF diagram for the complete stack frame layout.",
                "resolve_cluster": "true",
            },
            files={"solution_file": ("annotated_solution.pdf", io.BytesIO(teacher_pdf_bytes), "application/pdf")},
        )
        assert ans_res.status_code == 201, ans_res.text
        ans_data = ans_res.json()["answer"]
        assert ans_data["answer_attachment_name"] == "annotated_solution.pdf"
        answer_id = ans_data["id"]

        # 7. Student sees both attachment and teacher's solution file in My Doubts & downloads both
        s_list = client.get("/api/student/doubts", headers=s_headers)
        assert s_list.status_code == 200
        my_doubt = next(d for d in s_list.json()["data"] if d["id"] == doubt_id)
        assert len(my_doubt["attachments"]) == 1
        assert my_doubt["verified_answers"][0]["answer_attachment_name"] == "annotated_solution.pdf"

        s_detail = client.get(f"/api/student/doubts/{doubt_id}", headers=s_headers)
        assert s_detail.status_code == 200
        assert len(s_detail.json()["data"]["attachments"]) == 1
        assert s_detail.json()["data"]["verified_answers"][0]["answer_attachment_name"] == "annotated_solution.pdf"

        # Download student's own attachment
        s_att_dl = client.get(f"/api/student/doubts/attachments/{att_id}", headers=s_headers)
        assert s_att_dl.status_code == 200
        assert s_att_dl.content == student_img_bytes

        # Download teacher's solution file
        s_sol_dl = client.get(f"/api/student/doubts/{doubt_id}/answer-file/{answer_id}", headers=s_headers)
        assert s_sol_dl.status_code == 200
        assert s_sol_dl.content == teacher_pdf_bytes
    finally:
        storage_service.base_dir = orig_base_dir
