import httpx
from app.database import SessionLocal
from app.models.user import Student, Teacher
from app.security import create_access_token

client = httpx.Client(base_url="http://127.0.0.1:8000", timeout=30.0)
db = SessionLocal()

student = db.query(Student).filter(Student.id == 7).first() # Unnati
teacher = db.query(Teacher).filter(Teacher.id == 1).first() # Dr. S. K. Sharma

student_token = create_access_token({"sub": str(student.id), "role": "STUDENT", "college_id": student.student_code})
teacher_token = create_access_token({"sub": str(teacher.id), "role": "TEACHER", "college_id": teacher.teacher_code})

print("==================================================")
print("1. TEST STUDENT AI CHATBOT MESSAGE & FOLLOW-UP")
print("==================================================")
s_headers = {"Authorization": f"Bearer {student_token}"}
msg1 = "What is a binary search tree? Explain in 2 sentences."
res1 = client.post("/api/chatbot/student/message", json={"message": msg1}, headers=s_headers)
print("Student Msg 1 Status:", res1.status_code)
assert res1.status_code == 200, f"Failed: {res1.text}"
data1 = res1.json()
print("Student AI Response:", data1["response"])
conv_id = data1["conversation_id"]
assert conv_id is not None, "Missing conversation_id"

# Follow-up question with conversation_id
msg2 = "What is its search time complexity?"
res2 = client.post("/api/chatbot/student/message", json={"message": msg2, "conversation_id": conv_id}, headers=s_headers)
print("\nStudent Follow-up Status:", res2.status_code)
assert res2.status_code == 200, f"Failed: {res2.text}"
data2 = res2.json()
print("Student AI Follow-up Response:", data2["response"])

print("\n==================================================")
print("2. TEST TEACHER AI COPILOT MESSAGE & FOLLOW-UP")
print("==================================================")
t_headers = {"Authorization": f"Bearer {teacher_token}"}
t_msg1 = "Generate 2 MCQs on Stack data structure with correct answers."
t_res1 = client.post("/api/chatbot/teacher/message", json={"message": t_msg1}, headers=t_headers)
print("Teacher Msg 1 Status:", t_res1.status_code)
assert t_res1.status_code == 200, f"Failed: {t_res1.text}"
t_data1 = t_res1.json()
print("Teacher AI Response:\n", t_data1["response"])
t_conv_id = t_data1["conversation_id"]

# Teacher follow-up
t_msg2 = "Explain why the answer to Question 1 is correct."
t_res2 = client.post("/api/chatbot/teacher/message", json={"message": t_msg2, "conversation_id": t_conv_id}, headers=t_headers)
print("\nTeacher Follow-up Status:", t_res2.status_code)
assert t_res2.status_code == 200, f"Failed: {t_res2.text}"
t_data2 = t_res2.json()
print("Teacher AI Follow-up Response:\n", t_data2["response"])

print("\n==================================================")
print("3. TEST ROLE AUTHORIZATION & ISOLATION")
print("==================================================")
# Student trying to call teacher endpoint -> should fail
hack_teacher = client.post("/api/chatbot/teacher/message", json={"message": "hello"}, headers=s_headers)
print("Student calling teacher endpoint:", hack_teacher.status_code)
assert hack_teacher.status_code in (401, 403), "Security violation: Student reached teacher chatbot!"

# Teacher trying to call student endpoint -> should fail
hack_student = client.post("/api/chatbot/student/message", json={"message": "hello"}, headers=t_headers)
print("Teacher calling student endpoint:", hack_student.status_code)
assert hack_student.status_code in (401, 403), "Security violation: Teacher reached student chatbot!"

# Verify conversation isolation: teacher cannot access student conversation
cross_get = client.get(f"/api/chatbot/conversations/{conv_id}", headers=t_headers)
print("Teacher trying to get student conversation:", cross_get.status_code)
assert cross_get.status_code in (403, 404), "Data leakage: Teacher read student conversation!"

print("\n==================================================")
print("4. TEST CONVERSATION LIST & DELETE")
print("==================================================")
list_res = client.get("/api/chatbot/conversations", headers=s_headers)
print("Student conversation list count:", len(list_res.json().get("data", [])))
assert len(list_res.json().get("data", [])) >= 1

del_res = client.delete(f"/api/chatbot/conversations/{conv_id}", headers=s_headers)
print("Delete conversation status:", del_res.status_code)
assert del_res.status_code == 200

print("\n==================================================")
print("ALL CHATBOT E2E TESTS PASSED SUCCESSFULLY!")
print("==================================================")
db.close()
