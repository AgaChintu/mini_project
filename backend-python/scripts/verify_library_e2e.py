import httpx
from app.database import SessionLocal
from app.models.user import Student, Teacher
from app.security import create_access_token

client = httpx.Client(base_url="http://127.0.0.1:8000", timeout=30.0)
db = SessionLocal()

print("==================================================")
print("1. VERIFY TEACHER DASHBOARD PROFILE & NAME")
print("==================================================")
teacher = db.query(Teacher).filter(Teacher.id == 1).first() # Dr. S. K. Sharma
teacher_token = create_access_token({"sub": str(teacher.id), "role": "TEACHER", "college_id": teacher.teacher_code})
t_dash = client.get("/api/teacher/dashboard", headers={"Authorization": f"Bearer {teacher_token}"})
print(f"Teacher dashboard status: {t_dash.status_code}")
t_profile = t_dash.json().get("profile", {})
print(f"Teacher dynamic name: '{t_profile.get('full_name')}' (Department: {t_profile.get('department')})")
assert t_profile.get("full_name") == teacher.full_name, "Teacher name mismatch!"

print("\n==================================================")
print("2. VERIFY TEACHER LIBRARY SUBJECTS")
print("==================================================")
t_subs = client.get("/api/library/teacher/subjects", headers={"Authorization": f"Bearer {teacher_token}"})
print(f"Teacher subjects status: {t_subs.status_code}")
print(f"Assigned subjects: {[(s['id'], s['code'], s['faculty_category']) for s in t_subs.json().get('data', [])]}")

print("\n==================================================")
print("3. VERIFY STUDENT PROFILES AND SUBJECT VISIBILITY")
print("==================================================")
test_students = db.query(Student).all()
for s in test_students:
    s_token = create_access_token({"sub": str(s.id), "role": "STUDENT", "college_id": s.student_code})
    
    # Check dashboard profile
    s_dash = client.get("/api/student/dashboard", headers={"Authorization": f"Bearer {s_token}"})
    s_name = s_dash.json().get("profile", {}).get("full_name", s.full_name)
    
    # Check library subjects
    s_lib_subs = client.get("/api/library/student/subjects", headers={"Authorization": f"Bearer {s_token}"})
    subs_list = s_lib_subs.json().get("data", [])
    print(f"Student: '{s_name}' (ID: {s.id}, Sem: {s.current_semester}) -> Accessible subjects: {len(subs_list)}")
    assert len(subs_list) > 0, f"Student {s_name} got 0 subjects!"
    
    # Check resources for Subject 5 (Data Structures)
    s_res = client.get("/api/library/student/resources?subject_id=5", headers={"Authorization": f"Bearer {s_token}"})
    assert s_res.status_code == 200, f"Failed to get resources: {s_res.status_code}"
    resources = s_res.json().get("data", [])
    print(f"   -> Subject 5 has {len(resources)} resources visible to {s_name}")
    assert len(resources) >= 2, f"Expected at least 2 resources, got {len(resources)}"

print("\n==================================================")
print("4. VERIFY RESOURCE DOWNLOAD ENDPOINT")
print("==================================================")
s0 = test_students[0]
s0_token = create_access_token({"sub": str(s0.id), "role": "STUDENT", "college_id": s0.student_code})
dl_res = client.get("/api/library/student/resources/8/download", headers={"Authorization": f"Bearer {s0_token}"})
print(f"Download resource 8 status: {dl_res.status_code}, content length: {len(dl_res.content)} bytes")
assert dl_res.status_code == 200, "Download failed!"

print("\n==================================================")
print("ALL VERIFICATIONS PASSED SUCCESSFULLY!")
print("==================================================")
db.close()
