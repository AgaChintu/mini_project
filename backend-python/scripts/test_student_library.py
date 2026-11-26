import httpx
from app.database import SessionLocal
from app.models.user import Student, Teacher
from app.security import create_access_token

db = SessionLocal()
students = db.query(Student).all()
teachers = db.query(Teacher).all()

client = httpx.Client(base_url='http://127.0.0.1:8000')

print('=== TESTING ALL STUDENTS ON /api/library/student/subjects ===')
for s in students:
    token = create_access_token({'sub': str(s.id), 'role': 'STUDENT', 'college_id': s.student_code})
    res = client.get('/api/library/student/subjects', headers={'Authorization': f'Bearer {token}'})
    data = res.json()
    subs = data.get('data', [])
    print(f'Student {s.id} ({s.full_name}, sem={s.current_semester}): status={res.status_code}, subjects count={len(subs)}')
    for sub in subs:
        sub_id = sub['id']
        sub_name = sub['name']
        r_res = client.get(f'/api/library/student/resources?subject_id={sub_id}', headers={'Authorization': f'Bearer {token}'})
        r_data = r_res.json()
        res_list = r_data.get('data', [])
        if res_list:
            print(f'   -> Sub {sub_id} ({sub_name}): resources count={len(res_list)}')
            for r in res_list:
                print(f'        [{r["faculty_category"]}] {r["title"]} ({r["resource_type"]}) by {r["teacher_name"]}')

print('\n=== TESTING TEACHERS ON /api/library/teacher/subjects ===')
for t in teachers:
    token = create_access_token({'sub': str(t.id), 'role': 'TEACHER', 'college_id': t.teacher_code})
    res = client.get('/api/library/teacher/subjects', headers={'Authorization': f'Bearer {token}'})
    data = res.json()
    subs = data.get('data', [])
    print(f'Teacher {t.id} ({t.full_name}): status={res.status_code}, subjects count={len(subs)}')
    for sub in subs:
        print(f'   -> Assigned Sub {sub["id"]} ({sub["code"]} - {sub["name"]}): {sub["faculty_category"]}')

db.close()
