"""Check teacher assignments and uploaded resources"""
import sys; sys.path.insert(0, ".")
from app.database import SessionLocal
from app.models.academic_resource import AcademicResource
from app.models.assignment import SubjectTeacherAssignment, TeacherAssignment
from app.models.user import Teacher

db = SessionLocal()

print("=== SubjectTeacherAssignment (active) ===")
stas = db.query(SubjectTeacherAssignment).filter(SubjectTeacherAssignment.is_active == True).all()
for a in stas[:15]:
    t = db.query(Teacher).get(a.teacher_id)
    name = t.full_name if t else "?"
    print(f"  teacher={a.teacher_id}({name}) subject={a.subject_id} is_primary={a.is_primary}")

print("\n=== TeacherAssignment ===")
tas = db.query(TeacherAssignment).limit(10).all()
for a in tas[:10]:
    t = db.query(Teacher).get(a.teacher_id)
    name = t.full_name if t else "?"
    print(f"  teacher={a.teacher_id}({name}) subject={a.subject_id} section={a.section_id}")

print("\n=== Active AcademicResource ===")
resources = db.query(AcademicResource).filter(AcademicResource.status == "active").all()
for r in resources:
    print(f"  id={r.id} subject_id={r.subject_id} teacher_id={r.teacher_id} type={r.resource_type} title={r.title[:50]}")

db.close()
