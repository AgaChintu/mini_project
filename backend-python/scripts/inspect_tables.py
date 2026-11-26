import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    res = conn.execute(text("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        ORDER BY table_name;
    """))
    print("Tables in public schema:")
    for row in res:
        print(f"  {row[0]}")
