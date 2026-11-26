"""
ClariQ — Non-Demo User Cleanup Utility
Safely removes test/stale non-demo records while strictly preserving
official demo students (S001-S004) and demo teachers (T001-T011).
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path

# Add backend directory to sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
BACKEND_DIR = ROOT_DIR / "backend-python"
sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import SessionLocal
from app.models.user import Student, Teacher
from app.models.doubt import Doubt, DoubtAnswer
from app.models.assignment import TeacherAssignment

DEMO_STUDENT_CODES = {"S001", "S002", "S003", "S004"}
DEMO_TEACHER_CODES = {
    "T001", "T002", "T003", "T004", "T005",
    "T006", "T007", "T008", "T009", "T010", "T011"
}


def clean_non_demo_data(dry_run: bool = False):
    db = SessionLocal()
    try:
        print("=" * 60)
        print("CLARIQ DATABASE CLEANUP: AUDITING ACCOUNTS")
        print("=" * 60)

        students = db.query(Student).all()
        teachers = db.query(Teacher).all()

        preserved_students = [s for s in students if s.student_code in DEMO_STUDENT_CODES]
        stale_students = [s for s in students if s.student_code not in DEMO_STUDENT_CODES]

        preserved_teachers = [t for t in teachers if t.teacher_code in DEMO_TEACHER_CODES]
        stale_teachers = [t for t in teachers if t.teacher_code not in DEMO_TEACHER_CODES]

        print(f"Total Students: {len(students)}")
        print(f"  - Preserved Demo Students: {len(preserved_students)} {[s.student_code for s in preserved_students]}")
        print(f"  - Stale Non-Demo Students to remove: {len(stale_students)} {[s.student_code for s in stale_students]}")

        print(f"Total Teachers: {len(teachers)}")
        print(f"  - Preserved Demo Teachers: {len(preserved_teachers)} {[t.teacher_code for t in preserved_teachers]}")
        print(f"  - Stale Non-Demo Teachers to remove: {len(stale_teachers)} {[t.teacher_code for t in stale_teachers]}")

        if not stale_students and not stale_teachers:
            print("\nDatabase is already clean! Only official demo accounts exist.")
            return

        if dry_run:
            print("\n[DRY RUN] No records were modified.")
            return

        # Backup stale data before deletion
        backup_file = SCRIPT_DIR / f"cleanup_backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        backup_data = {
            "students": [{"id": s.id, "code": s.student_code, "name": s.full_name, "email": s.email} for s in stale_students],
            "teachers": [{"id": t.id, "code": t.teacher_code, "name": t.full_name, "email": t.email} for t in stale_teachers],
        }
        with open(backup_file, "w") as f:
            json.dump(backup_data, f, indent=2)
        print(f"\nCreated backup at: {backup_file}")

        # Remove stale students and cascade doubts
        for s in stale_students:
            db.delete(s)

        # Remove stale teachers and cascade assignments
        for t in stale_teachers:
            db.delete(t)

        db.commit()
        print("\nSuccessfully cleaned stale records while preserving all demo data!")

    except Exception as e:
        db.rollback()
        print(f"\nError during cleanup: {e}", file=sys.stderr)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    clean_non_demo_data(dry_run=dry)
