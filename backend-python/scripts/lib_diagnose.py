"""
Diagnose why student library shows No subjects / 0 resources.
Run from backend-python directory:
  python scripts/lib_diagnose.py
"""
import sys
sys.path.insert(0, ".")

from sqlalchemy import inspect as sa_inspect, text
from app.database import SessionLocal
from app.models.user import Student
from app.models.academic import Subject, SectionGroupMember, SubjectOffering

db = SessionLocal()

# --- 1. Student model columns ---
cols = [c.key for c in sa_inspect(Student).mapper.columns]
print("Student columns:", cols)
print()

# --- 2. All DB tables ---
tables_q = db.execute(text(
    "SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name"
)).fetchall()
print("Tables:", [t[0] for t in tables_q])
print()

# --- 3. First 5 students ---
students = db.query(Student).limit(5).all()
for stu in students:
    id_field = getattr(stu, 'college_id', None) or getattr(stu, 'student_id', None) or stu.id
    sec = stu.section
    sem = sec.semester if sec else None
    cur_sem = getattr(stu, 'current_semester', None)
    if cur_sem is None and sem:
        cur_sem = sem.semester_number

    # Method 1: SectionGroupMember (library.py uses this)
    group_ids = []
    if sec:
        gids = db.query(SectionGroupMember.section_group_id).filter(
            SectionGroupMember.section_id == sec.id
        ).all()
        group_ids = [g[0] for g in gids]

    sub_via_groups = []
    if group_ids:
        sub_via_groups = [
            s[0] for s in db.query(SubjectOffering.subject_id).filter(
                SubjectOffering.section_group_id.in_(group_ids)
            ).all()
        ]

    # Method 2: semester_number (dashboard uses this)
    sub_via_sem = []
    if cur_sem:
        sub_via_sem = [
            s.id for s in db.query(Subject).filter(
                Subject.semester_number == cur_sem,
                Subject.is_active == True
            ).all()
        ]

    print(f"Student id={stu.id}({id_field}) | section_id={sec.id if sec else None} | cur_sem={cur_sem}")
    print(f"  group_ids={group_ids}")
    print(f"  subjects_via_SectionGroupMember={sub_via_groups}")
    print(f"  subjects_via_semester_number={sub_via_sem}")
    print()

# --- 4. SectionGroupMember count ---
sgm_count = db.query(SectionGroupMember).count()
so_count = db.query(SubjectOffering).count()
print(f"SectionGroupMember rows: {sgm_count}")
print(f"SubjectOffering rows: {so_count}")
print()

# --- 5. AcademicResource count ---
from app.models.academic_resource import AcademicResource
res_count = db.query(AcademicResource).filter(AcademicResource.status == 'active').count()
print(f"Active AcademicResource rows: {res_count}")
if res_count > 0:
    sample = db.query(AcademicResource).filter(AcademicResource.status == 'active').limit(3).all()
    for r in sample:
        print(f"  id={r.id} subject_id={r.subject_id} type={r.resource_type} title={r.title[:40]}")

db.close()
