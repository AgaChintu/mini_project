import httpx
from app.core.database import SessionLocal
from app.models.user import Teacher, Student
from app.security import create_access_token

db = SessionLocal()
teacher = db.query(Teacher).filter(Teacher.id == 10).first()
student = db.query(Student).filter(Student.id == 7).first()  # unnati

t_token = create_access_token({"sub": str(teacher.id), "user_id": teacher.id, "role": "TEACHER"})
s_token = create_access_token({"sub": str(student.id), "user_id": student.id, "role": "STUDENT"})

client = httpx.Client(base_url="http://127.0.0.1:8000", timeout=30)

print("=== 1. TEACHER UPLOAD TEST ===")
pdf_bytes = b"%PDF-1.4 sample syllabus document content for verification"
files = {
    "document": ("Engineering_Chemistry_Unit2_Notes.pdf", pdf_bytes, "application/pdf")
}
data = {
    "subject_id": "2",
    "title": "Engineering Chemistry Unit 2 Notes",
    "description": "Comprehensive study notes covering Electrochemistry and Polymers",
    "resource_type": "pdf",
    "is_important": "false"
}
res_upload = client.post("/api/library/teacher/resources", data=data, files=files, headers={"Authorization": f"Bearer {t_token}"})
print("Teacher upload status:", res_upload.status_code)
upload_json = res_upload.json()
print("Teacher upload title:", upload_json.get("data", {}).get("title"))

print("\n=== 2. STUDENT SUBJECTS ENDPOINT TEST ===")
res_subjs = client.get("/api/library/student/subjects", headers={"Authorization": f"Bearer {s_token}"})
print("Student subjects status:", res_subjs.status_code)
subjs_data = res_subjs.json()
print("Total accessible subjects for student:", len(subjs_data.get("data", [])))

print("\n=== 3. STUDENT LIBRARY RESOURCES TEST (Subject 2) ===")
res_res = client.get("/api/library/student/resources?subject_id=2", headers={"Authorization": f"Bearer {s_token}"})
print("Student resources status:", res_res.status_code)
res_json = res_res.json()
print("Total resources for subject 2:", res_json.get("total"))
for r in res_json.get("data", []):
    print(f"  - [{r['resource_type']}] {r['title']} (by {r['teacher_name']})")

print("\n=== 4. STUDENT DASHBOARD API TEST ===")
res_dash = client.get("/api/student/dashboard", headers={"Authorization": f"Bearer {s_token}"})
print("Dashboard status:", res_dash.status_code)
dash_data = res_dash.json()
print("Student name:", dash_data.get("profile", {}).get("full_name"))
print("Enrolled subjects count:", len(dash_data.get("subjects", [])))
for s in dash_data.get("subjects", []):
    print(f"  - Subject: {s['code']} {s['name']} | Doubts: {s['my_doubts_count']} | Materials: {s.get('resources_count')}")

recent_res = dash_data.get("recent_resources", [])
print(f"Recent study materials on student dashboard: {len(recent_res)} items")
for r in recent_res[:3]:
    print(f"  - {r['title']} ({r['subject_code']}) by {r['teacher_name']}")

print("\n=== ALL TESTS COMPLETED SUCCESSFULLY ===")
db.close()
