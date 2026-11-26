"""
End-to-end: verify student library subjects and resource visibility.
Run from backend-python directory:
  python scripts/verify_student_library.py
"""
import sys, time; sys.path.insert(0, ".")
time.sleep(3)  # Let server start if running fresh

import httpx
from app.security import create_access_token
from app.database import SessionLocal
from app.models.user import Student

db = SessionLocal()
# Use the student in section 7 (semester 3)
student = db.query(Student).filter(Student.section_id == 7).first()
print(f"Testing as: id={student.id} full_name={student.full_name} section_id={student.section_id} cur_sem={student.current_semester}")
db.close()

token = create_access_token({"sub": str(student.id), "role": "STUDENT"})
hdrs = {"Authorization": f"Bearer {token}"}

# 1. Test /api/library/student/subjects
r = httpx.get("http://127.0.0.1:8000/api/library/student/subjects", headers=hdrs, timeout=15)
print(f"\n/student/subjects => HTTP {r.status_code}")
subjects = r.json().get("data", [])
print(f"  Subjects returned: {[(s['id'], s['code'], s['name']) for s in subjects]}")
assert len(subjects) > 0, "FAIL: No subjects returned for student!"
print("  PASS: Subjects loaded correctly")

# 2. Test /api/library/student/resources for subject 5 (Data Structures)
sub5 = next((s for s in subjects if s["id"] == 5), None)
if sub5:
    r2 = httpx.get(f"http://127.0.0.1:8000/api/library/student/resources?subject_id=5", headers=hdrs, timeout=15)
    print(f"\n/student/resources?subject_id=5 => HTTP {r2.status_code}")
    resources = r2.json().get("data", [])
    print(f"  Resources returned: {len(resources)}")
    for res in resources:
        print(f"    id={res['id']} type={res['resource_type']} category={res['faculty_category']} title={res['title'][:50]}")
    if len(resources) > 0:
        print("  PASS: Resources are visible to student!")
    else:
        print("  NOTE: No resources uploaded yet for subject 5. Upload one from teacher Library page to test.")
else:
    print("\nSubject 5 not in student's list — checking first subject")
    if subjects:
        sub_id = subjects[0]["id"]
        r2 = httpx.get(f"http://127.0.0.1:8000/api/library/student/resources?subject_id={sub_id}", headers=hdrs, timeout=15)
        print(f"/student/resources?subject_id={sub_id} => HTTP {r2.status_code}")
        resources = r2.json().get("data", [])
        print(f"  Resources: {len(resources)}")
        for res in resources:
            print(f"    id={res['id']} type={res['resource_type']} title={res['title'][:50]}")

print("\nALL CHECKS COMPLETE")
