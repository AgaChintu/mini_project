import sys
from pathlib import Path

# Add ClariQ root directory to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.migrate_mysql_to_supabase import MIGRATION_TABLES, migrate


def test_migration_table_dependencies():
    """Verify table dependency order prevents foreign key violations."""
    assert MIGRATION_TABLES.index("academic_years") < MIGRATION_TABLES.index("semesters")
    assert MIGRATION_TABLES.index("semesters") < MIGRATION_TABLES.index("sections")
    assert MIGRATION_TABLES.index("sections") < MIGRATION_TABLES.index("students")
    assert MIGRATION_TABLES.index("subjects") < MIGRATION_TABLES.index("syllabus_units")
    assert MIGRATION_TABLES.index("syllabus_units") < MIGRATION_TABLES.index("syllabus_topics")
    assert MIGRATION_TABLES.index("syllabus_topics") < MIGRATION_TABLES.index("syllabus_subtopics")
    assert MIGRATION_TABLES.index("students") < MIGRATION_TABLES.index("doubts")
    assert MIGRATION_TABLES.index("doubts") < MIGRATION_TABLES.index("doubt_answers")
    assert MIGRATION_TABLES.index("doubts") < MIGRATION_TABLES.index("attachments")
    assert MIGRATION_TABLES.index("doubts") < MIGRATION_TABLES.index("library_entries")
    assert MIGRATION_TABLES.index("library_entries") < MIGRATION_TABLES.index("saved_entries")


def test_migration_preflight_blocks_when_mysql_offline():
    """Ensure migration returns False and does not crash when MySQL is offline."""
    result = migrate(dry_run=True)
    assert result is False
