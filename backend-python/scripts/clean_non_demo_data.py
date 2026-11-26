import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionLocal
from app.models.user import Student, Teacher
from app.models.doubt import Doubt, DoubtAnswer, Attachment, DoubtSubtopic
from app.models.library import SavedEntry, LibraryEntry
from app.models.session import SessionDoubt
from app.models.assignment import TeacherAssignment

DEMO_STUDENT_CODES = {"S001", "S002", "S003", "S004"}
DEMO_TEACHER_CODES = {
    "T001", "T002", "T003", "T004", "T005", "T006",
    "T007", "T008", "T009", "T010", "T011"
}

def clean_database(dry_run=True):
    db = SessionLocal()
    try:
        non_demo_students = db.query(Student).filter(
            ~Student.student_code.in_(DEMO_STUDENT_CODES)
        ).all()

        non_demo_teachers = db.query(Teacher).filter(
            ~Teacher.teacher_code.in_(DEMO_TEACHER_CODES)
        ).all()

        print(f"Dry Run: {dry_run}")
        print(f"Found {len(non_demo_students)} non-demo students to remove.")
        print(f"Found {len(non_demo_teachers)} non-demo teachers to remove.")

        if len(non_demo_students) == 0 and len(non_demo_teachers) == 0:
            print("Database is already clean! No non-demo records found.")
            return

        if dry_run:
            print("[DRY RUN] No records were deleted.")
            return

        # Safe transactional deletion
        # 1. For each non-demo student, cleanly remove child doubts, saved entries, etc.
        for student in non_demo_students:
            print(f"Cleaning data for student {student.student_code} ({student.email})...")
            # Delete bookmarks
            db.query(SavedEntry).filter(SavedEntry.student_id == student.id).delete(synchronize_session=False)
            db.query(SessionDoubt).filter(SessionDoubt.student_id == student.id).delete(synchronize_session=False)

            # Doubts submitted by this student
            student_doubts = db.query(Doubt).filter(Doubt.student_id == student.id).all()
            for doubt in student_doubts:
                # Delete answers, attachments, subtopic mappings, library entries
                db.query(LibraryEntry).filter(LibraryEntry.doubt_id == doubt.id).delete(synchronize_session=False)
                db.query(DoubtAnswer).filter(DoubtAnswer.doubt_id == doubt.id).delete(synchronize_session=False)
                db.query(Attachment).filter(Attachment.doubt_id == doubt.id).delete(synchronize_session=False)
                db.query(DoubtSubtopic).filter(DoubtSubtopic.doubt_id == doubt.id).delete(synchronize_session=False)
                db.delete(doubt)

            db.delete(student)

        # 2. For each non-demo teacher
        for teacher in non_demo_teachers:
            print(f"Cleaning data for teacher {teacher.teacher_code} ({teacher.email})...")
            # Remove assignments
            db.query(TeacherAssignment).filter(TeacherAssignment.teacher_id == teacher.id).delete(synchronize_session=False)
            # Remove answers published by non-demo teacher
            db.query(DoubtAnswer).filter(DoubtAnswer.teacher_id == teacher.id).delete(synchronize_session=False)
            db.delete(teacher)

        db.commit()
        print("Database cleanup committed successfully!")
    except Exception as e:
        db.rollback()
        print(f"Error during cleanup: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    dry = "--execute" not in sys.argv
    clean_database(dry_run=dry)
