import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.main import app

def verify_all_demo_accounts():
    client = TestClient(app)

    demo_students = [
        ("S001", "s001@clariq.local", "Aarav Sharma"),
        ("S002", "s002@clariq.local", "Diya Patel"),
        ("S003", "s003@clariq.local", "Rohan Verma"),
        ("S004", "s004@clariq.local", "Ananya Iyer"),
    ]

    demo_teachers = [
        ("T001", "sksharma@clariq.local", "Dr. S. K. Sharma"),
        ("T002", "averma@clariq.local", "Dr. Anita Verma"),
        ("T003", "rmehta@clariq.local", "Prof. Rajiv Mehta"),
        ("T004", "pnair@clariq.local", "Dr. Priya Nair"),
        ("T005", "vgupta@clariq.local", "Prof. Vikas Gupta"),
        ("T006", "nsingh@clariq.local", "Prof. Neha Singh"),
        ("T007", "apandey@clariq.local", "Dr. Alok Pandey"),
        ("T008", "srao@clariq.local", "Prof. Sunita Rao"),
        ("T009", "mtiwari@clariq.local", "Dr. Manish Tiwari"),
        ("T010", "pjoshi@clariq.local", "Prof. Pooja Joshi"),
        ("T011", "rmishra@clariq.local", "Dr. Rakesh Mishra"),
    ]

    print("\n--- AUDITING ALL DEMO STUDENT ACCOUNTS ---")
    for code, email, name in demo_students:
        # 1. Login with student code
        r1 = client.post("/api/auth/login", json={"college_id": code, "password": "student123"})
        assert r1.status_code == 200, f"Demo student {code} failed login by ID: {r1.text}"
        token = r1.json()["access_token"]

        # 2. Login with email
        r2 = client.post("/api/auth/login", json={"college_id": email, "password": "student123"})
        assert r2.status_code == 200, f"Demo student {code} failed login by email: {r2.text}"

        # 3. Call /me
        me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200, f"Demo student {code} /me failed: {me.text}"
        data = me.json()
        assert data["college_id"] == code
        assert data["role"] == "STUDENT"
        print(f"  [OK] Student {code} ({name}) - ID & Email login verified")

    print("\n--- AUDITING ALL DEMO TEACHER ACCOUNTS ---")
    for code, email, name in demo_teachers:
        # 1. Login with teacher code
        r1 = client.post("/api/auth/login", json={"college_id": code, "password": "teacher123"})
        assert r1.status_code == 200, f"Demo teacher {code} failed login by ID: {r1.text}"
        token = r1.json()["access_token"]

        # 2. Login with email
        r2 = client.post("/api/auth/login", json={"college_id": email, "password": "teacher123"})
        assert r2.status_code == 200, f"Demo teacher {code} failed login by email: {r2.text}"

        # 3. Call /me
        me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200, f"Demo teacher {code} /me failed: {me.text}"
        data = me.json()
        assert data["college_id"] == code
        assert data["role"] == "TEACHER"
        print(f"  [OK] Teacher {code} ({name}) - ID & Email login verified")

    print("\nALL 15 DEMO ACCOUNTS (4 STUDENTS + 11 TEACHERS) ARE ACTIVE AND FUNCTIONING PROPERLY!\n")

if __name__ == "__main__":
    verify_all_demo_accounts()
