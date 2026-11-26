import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    res = conn.execute(text("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'subject_teacher_assignments'
        ORDER BY ordinal_position;
    """))
    print("Columns in 'subject_teacher_assignments':")
    for row in res:
        print(f"  {row[0]}: {row[1]} (nullable: {row[2]})")

    cnt = conn.execute(text("SELECT COUNT(*) FROM subject_teacher_assignments")).scalar()
    print(f"Total rows in 'subject_teacher_assignments': {cnt}")
