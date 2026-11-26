import sys
import os
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionLocal
from app.models.user import Student, Teacher
from app.models.doubt import Doubt, DoubtAnswer
from app.models.academic import Subject, Section, Semester, AcademicYear
from app.models.assignment import TeacherAssignment

DEMO_STUDENT_CODES = {"S001", "S002", "S003", "S004"}
DEMO_TEACHER_CODES = {
    "T001", "T002", "T003", "T004", "T005", "T006",
    "T007", "T008", "T009", "T010", "T011"
}

def audit_database():
    db = SessionLocal()
    try:
        all_students = db.query(Student).all()
        all_teachers = db.query(Teacher).all()

        demo_students = [s for s in all_students if s.student_code in DEMO_STUDENT_CODES]
        non_demo_students = [s for s in all_students if s.student_code not in DEMO_STUDENT_CODES]

        demo_teachers = [t for t in all_teachers if t.teacher_code in DEMO_TEACHER_CODES]
        non_demo_teachers = [t for t in all_teachers if t.teacher_code not in DEMO_TEACHER_CODES]

        total_doubts = db.query(Doubt).count()
        total_answers = db.query(DoubtAnswer).count()
        total_subjects = db.query(Subject).count()

        print("=== DATABASE AUDIT REPORT ===")
        print(f"Total Students:     {len(all_students)}")
        print(f"  - Demo Students:     {len(demo_students)} ({[s.student_code for s in demo_students]})")
        print(f"  - Non-Demo Students: {len(non_demo_students)} ({[s.student_code for s in non_demo_students]})")
        print(f"Total Teachers:     {len(all_teachers)}")
        print(f"  - Demo Teachers:     {len(demo_teachers)} ({[t.teacher_code for t in demo_teachers]})")
        print(f"  - Non-Demo Teachers: {len(non_demo_teachers)} ({[t.teacher_code for t in non_demo_teachers]})")
        print(f"Total Doubts:       {total_doubts}")
        print(f"Total Answers:      {total_answers}")
        print(f"Total Subjects:     {total_subjects}")
        print("=============================")

        return {
            "total_students": len(all_students),
            "demo_students": len(demo_students),
            "non_demo_students": len(non_demo_students),
            "total_teachers": len(all_teachers),
            "demo_teachers": len(demo_teachers),
            "non_demo_teachers": len(non_demo_teachers),
            "non_demo_student_records": non_demo_students,
            "non_demo_teacher_records": non_demo_teachers,
        }
    finally:
        db.close()

if __name__ == "__main__":
    audit_database()
