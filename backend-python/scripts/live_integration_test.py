import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal
from app.models.user import Student, Teacher
from app.models.doubt import Doubt, DoubtAnswer
from app.models.academic import Subject, Section

def run_live_integration():
    client = TestClient(app)
    db = SessionLocal()

    test_student_email = "live.part2.test@clariq.edu"
    test_student_code = None

    try:
        print("\n--- STEP 1: DYNAMIC STUDENT REGISTRATION ---")
        reg_payload = {
            "full_name": "Rohan Deshmukh",
            "email": test_student_email,
            "password": "LivePassword123!",
            "confirm_password": "LivePassword123!",
            "department": "Computer Science & Engineering",
            "semester_number": 3,
            "section_code": "AIML",
        }
        res = client.post("/api/auth/student/register", json=reg_payload)
        assert res.status_code == 201, f"Student registration failed: {res.text}"
        reg_data = res.json()
        test_student_code = reg_data["college_id"]
        student_token = reg_data["access_token"]
        student_headers = {"Authorization": f"Bearer {student_token}"}

        print(f"Registered student: {reg_data['name']} with ID: {test_student_code}")
        assert test_student_code.startswith("STU-")
        assert test_student_code not in ["S001", "S002", "S003", "S004"]
        print("Dynamic ID generation: PASSED")

        print("\n--- STEP 2: MULTI-IDENTIFIER LOGIN ---")
        # Login with College ID
        login_id_res = client.post("/api/auth/login", json={
            "college_id": test_student_code,
            "password": "LivePassword123!",
        })
        assert login_id_res.status_code == 200, f"Login with ID failed: {login_id_res.text}"
        # Login with Email
        login_email_res = client.post("/api/auth/login", json={
            "college_id": test_student_email,
            "password": "LivePassword123!",
        })
        assert login_email_res.status_code == 200, f"Login with email failed: {login_email_res.text}"
        print("Login with College ID and Email: PASSED")

        print("\n--- STEP 3: STUDENT DASHBOARD OVERVIEW ---")
        dash_res = client.get("/api/student/dashboard", headers=student_headers)
        assert dash_res.status_code == 200, f"Dashboard failed: {dash_res.text}"
        dash_data = dash_res.json()
        assert dash_data["profile"]["full_name"] == "Rohan Deshmukh"
        assert len(dash_data["subjects"]) > 0
        first_subject = dash_data["subjects"][0]
        subject_id = first_subject["id"]
        print(f"Profile dynamic loaded: {dash_data['profile']['full_name']}")
        print(f"Subjects assigned: {[s['name'] for s in dash_data['subjects']]}")
        print("Student dashboard: PASSED")

        print("\n--- STEP 4: ANONYMOUS DOUBT SUBMISSION ---")
        doubt_payload = {
            "subject_id": subject_id,
            "title": "Query regarding QuickSort worst-case time complexity",
            "description": "Does QuickSort degrade to O(N^2) if the pivot is consistently chosen as the maximum element?",
        }
        doubt_res = client.post("/api/student/doubts", headers=student_headers, json=doubt_payload)
        assert doubt_res.status_code == 201, f"Doubt submission failed: {doubt_res.text}"
        doubt_data = doubt_res.json()
        created_doubt_id = doubt_data["doubt"]["id"]
        doubt_code = doubt_data["doubt"]["doubt_code"]
        print(f"Submitted doubt: {doubt_code} (ID: {created_doubt_id})")
        print("Anonymous doubt submission: PASSED")

        print("\n--- STEP 5: TEACHER DASHBOARD & PRIVACY AUDIT ---")
        # Login as teacher T001
        t_login_res = client.post("/api/auth/login", json={
            "college_id": "T001",
            "password": "teacher123",
        })
        assert t_login_res.status_code == 200, f"Teacher login failed: {t_login_res.text}"
        t_token = t_login_res.json()["access_token"]
        teacher_headers = {"Authorization": f"Bearer {t_token}"}

        t_dash_res = client.get("/api/teacher/dashboard", headers=teacher_headers)
        assert t_dash_res.status_code == 200, f"Teacher dash failed: {t_dash_res.text}"
        print(f"Teacher logged in: {t_dash_res.json()['profile']['full_name']}")

        # Fetch subject doubts as teacher
        t_doubts_res = client.get(f"/api/teacher/subjects/{subject_id}/doubts", headers=teacher_headers)
        assert t_doubts_res.status_code == 200, f"Teacher doubts view failed: {t_doubts_res.text}"
        t_doubts_data = t_doubts_res.json()

        # PRIVACY AUDIT: Ensure student identity is completely stripped
        t_json_str = str(t_doubts_data).lower()
        assert "rohan" not in t_json_str, "CRITICAL: Student full name leaked in teacher API!"
        assert test_student_email.lower() not in t_json_str, "CRITICAL: Student email leaked in teacher API!"
        assert str(reg_data["user_id"]) not in [
            str(d.get("student_id"))
            for cluster in t_doubts_data.get("clusters", [])
            for d in cluster.get("doubts", [])
        ], "CRITICAL: Student database ID leaked in teacher API!"
        print("PRIVACY AUDIT: 100% PASSED - No student names, emails, or IDs exposed to teacher")

        print("\n--- STEP 6: HUMAN-IN-THE-LOOP ANSWER VERIFICATION ---")
        answer_payload = {
            "answer_text": "Yes, if the pivot is always the maximum or minimum element, the recursion tree becomes skewed of depth N, yielding O(N^2) complexity. Using randomized pivot selection or median-of-three mitigates this.",
            "resource_url": "https://clariq.edu/resources/quicksort-analysis.pdf",
            "resolve_cluster": True,
        }
        ans_res = client.post(f"/api/teacher/doubts/{created_doubt_id}/answer", headers=teacher_headers, json=answer_payload)
        assert ans_res.status_code == 201, f"Answer publish failed: {ans_res.text}"
        print("Published verified answer: PASSED")

        print("\n--- STEP 7: STUDENT VERIFIED ANSWER RETRIEVAL ---")
        my_doubts_res = client.get("/api/student/doubts", headers=student_headers)
        assert my_doubts_res.status_code == 200
        my_doubts = my_doubts_res.json()["data"]
        target_doubt = next((d for d in my_doubts if d["id"] == created_doubt_id), None)
        assert target_doubt is not None, "Student could not find submitted doubt"
        assert target_doubt["status"] == "resolved", f"Status expected 'resolved', got '{target_doubt['status']}'"
        assert len(target_doubt["verified_answers"]) >= 1
        print(f"Verified Answer received by student from: {target_doubt['verified_answers'][0]['teacher_name']}")
        print("Answer verification flow: PASSED")

        print("\n--- STEP 8: SAFE TEST RECORD CLEANUP & CASCADE TEST ---")
        # Deleting the student should cleanly cascade delete the doubt and answers without errors!
        student_obj = db.query(Student).filter(Student.student_code == test_student_code).first()
        if student_obj:
            db.delete(student_obj)
            db.commit()
            print("Cascading delete of student test record: SUCCESSFUL")

        # Confirm doubt is also deleted
        remaining_doubt = db.query(Doubt).filter(Doubt.id == created_doubt_id).first()
        assert remaining_doubt is None, "Doubt should have been cascade-deleted with student"
        print("Doubt cascade deletion verified: CONFIRMED")

        print("\n==========================================")
        print("ALL LIVE INTEGRATION TESTS PASSED 100%!")
        print("==========================================")

    except Exception as e:
        db.rollback()
        print(f"\nTEST RUN FAILED: {e}")
        import traceback
        traceback.print_exc()
        # Clean up if student still exists
        if test_student_code:
            try:
                s = db.query(Student).filter(Student.student_code == test_student_code).first()
                if s:
                    db.delete(s)
                    db.commit()
            except Exception:
                db.rollback()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    run_live_integration()
