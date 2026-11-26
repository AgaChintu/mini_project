import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    res = conn.execute(text('''
        SELECT tc.table_name, kcu.column_name, tc.constraint_name, rc.delete_rule
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.referential_constraints AS rc ON tc.constraint_name = rc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_name IN ('doubts','doubt_answers','attachments','saved_entries','session_doubts')
        ORDER BY tc.table_name, kcu.column_name;
    '''))
    for row in res:
        print(row)
