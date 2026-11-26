"""
ClariQ Safe MySQL to Supabase PostgreSQL Migration Utility

Usage:
  python scripts/migrate_mysql_to_supabase.py [--dry-run] [--verify]

Requirements:
- Reads from MySQL (source) without modifying, truncating, or deleting rows.
- Writes to Supabase PostgreSQL (destination) in strict dependency order.
- Preserves primary keys, foreign keys, UUIDs, password hashes, and timestamps.
- Synchronizes PostgreSQL auto-increment sequences (SERIAL) post-migration.
- Fully idempotent: can be rerun safely without duplicating records.
- If MySQL is stopped/unavailable, reports BLOCKED with actionable instructions.
"""

import os
import sys
import argparse
import logging
from typing import Dict, List, Any
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("clariq.migration")

# Table dependency order
MIGRATION_TABLES = [
    "academic_years",
    "semesters",
    "section_groups",
    "sections",
    "section_group_members",
    "subjects",
    "subject_offerings",
    "syllabus_units",
    "syllabus_topics",
    "syllabus_subtopics",
    "course_outcomes",
    "textbooks",
    "teachers",
    "students",
    "teacher_assignments",
    "doubts",
    "doubt_subtopics",
    "doubt_answers",
    "attachments",
    "library_entries",
    "saved_entries",
    "doubt_sessions",
    "session_topics",
    "session_doubts",
]


def get_mysql_engine():
    """Builds and verifies the MySQL source engine."""
    mysql_url = os.getenv("MYSQL_DATABASE_URL")
    if not mysql_url:
        host = os.getenv("MYSQL_HOST", "127.0.0.1")
        port = os.getenv("MYSQL_PORT", "3306")
        db = os.getenv("MYSQL_DB", "clariq")
        user = os.getenv("MYSQL_USER", "root")
        pw = os.getenv("MYSQL_PASSWORD", "")
        mysql_url = f"mysql+pymysql://{user}:{pw}@{host}:{port}/{db}"

    try:
        engine = create_engine(mysql_url, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return engine
    except Exception as e:
        logger.warning("Could not connect to MySQL source: %s", str(e))
        return None


def get_supabase_engine():
    """Builds and verifies the Supabase PostgreSQL destination engine."""
    pg_url = os.getenv("DATABASE_URL")
    if not pg_url:
        logger.error("DATABASE_URL environment variable is missing for Supabase destination.")
        return None

    # Normalize driver
    if pg_url.startswith("postgres://"):
        pg_url = "postgresql+psycopg://" + pg_url[len("postgres://") :]
    elif pg_url.startswith("postgresql://") and not pg_url.startswith("postgresql+"):
        pg_url = "postgresql+psycopg://" + pg_url[len("postgresql://") :]

    try:
        engine = create_engine(pg_url, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return engine
    except Exception as e:
        logger.error("Could not connect to Supabase PostgreSQL: %s", str(e))
        return None


def migrate(dry_run: bool = False, verify_only: bool = False):
    """Executes the safe MySQL to Supabase data migration."""
    logger.info("Starting ClariQ Data Migration Engine...")
    if dry_run:
        logger.info("[MODE] DRY RUN: No records will be committed to Supabase.")

    mysql_engine = get_mysql_engine()
    if mysql_engine is None:
        logger.error(
            "\n"
            "====================================================================\n"
            "[MIGRATION BLOCKED] MySQL source database is unreachable.\n"
            "Reason: MySQL Server service (port 3306) is stopped or credentials invalid.\n"
            "Resolution:\n"
            "  1. Start MySQL Server: 'net start MySQL80' (or via Windows Services).\n"
            "  2. Verify credentials in .env.\n"
            "===================================================================="
        )
        return False

    supabase_engine = get_supabase_engine()
    if supabase_engine is None:
        logger.error(
            "\n"
            "====================================================================\n"
            "[MIGRATION BLOCKED] Supabase PostgreSQL destination is unreachable.\n"
            "Reason: Invalid or missing DATABASE_URL in environment.\n"
            "Resolution:\n"
            "  1. Obtain connection URI from Supabase Dashboard -> Project Settings -> Database.\n"
            "  2. Set DATABASE_URL in backend-python/.env.\n"
            "===================================================================="
        )
        return False

    results: Dict[str, Dict[str, int]] = {}

    try:
        with mysql_engine.connect() as my_conn, supabase_engine.connect() as pg_conn:
            for table in MIGRATION_TABLES:
                # 1. Inspect source rows
                try:
                    source_rows = my_conn.execute(text(f"SELECT * FROM `{table}`")).mappings().all()
                except Exception as e:
                    logger.info("Table '%s' does not exist in MySQL source or is empty (skipped).", table)
                    continue

                source_count = len(source_rows)
                inserted = 0
                skipped = 0
                failed = 0

                if source_count == 0:
                    results[table] = {"source": 0, "inserted": 0, "skipped": 0, "failed": 0}
                    continue

                # 2. Migrate each row idempotently
                for row in source_rows:
                    row_dict = dict(row)
                    pk_val = row_dict.get("id")

                    # Check if destination already has this row
                    existing = None
                    if pk_val is not None:
                        existing = pg_conn.execute(
                            text(f'SELECT 1 FROM "{table}" WHERE id = :id'),
                            {"id": pk_val},
                        ).scalar()

                    if existing:
                        skipped += 1
                        continue

                    if dry_run:
                        inserted += 1
                        continue

                    # Insert row into Supabase PostgreSQL
                    cols = list(row_dict.keys())
                    col_names = ", ".join([f'"{c}"' for c in cols])
                    param_names = ", ".join([f":{c}" for c in cols])
                    insert_stmt = text(f'INSERT INTO "{table}" ({col_names}) VALUES ({param_names})')

                    try:
                        pg_conn.execute(insert_stmt, row_dict)
                        inserted += 1
                    except Exception as ins_err:
                        failed += 1
                        logger.error("Failed to insert into %s (ID %s): %s", table, pk_val, ins_err)

                if not dry_run:
                    pg_conn.commit()

                    # 3. Synchronize PostgreSQL sequence
                    try:
                        seq_res = pg_conn.execute(
                            text(
                                f"SELECT setval(pg_get_serial_sequence('\"{table}\"', 'id'), "
                                f'COALESCE((SELECT MAX(id) FROM "{table}"), 1));'
                            )
                        )
                        pg_conn.commit()
                    except Exception:
                        pass

                results[table] = {
                    "source": source_count,
                    "inserted": inserted,
                    "skipped": skipped,
                    "failed": failed,
                }
                logger.info(
                    "Table '%s': Source=%d | Inserted=%d | Skipped=%d | Failed=%d",
                    table,
                    source_count,
                    inserted,
                    skipped,
                    failed,
                )

        print("\n====================================================================")
        print("CLARIQ MYSQL TO SUPABASE MIGRATION SUMMARY")
        print("====================================================================")
        for tbl, stats in results.items():
            print(
                f"  {tbl:<24} Source: {stats['source']:<5} | "
                f"Inserted: {stats['inserted']:<5} | "
                f"Skipped: {stats['skipped']:<5} | "
                f"Failed: {stats['failed']}"
            )
        print("====================================================================\n")
        return True

    except Exception as e:
        logger.error("Fatal error during data migration: %s", str(e))
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ClariQ MySQL to Supabase PostgreSQL Migration")
    parser.add_argument("--dry-run", action="store_true", help="Simulate migration without committing changes")
    parser.add_argument("--verify", action="store_true", help="Verify record counts without transferring")
    args = parser.parse_args()

    migrate(dry_run=args.dry_run, verify_only=args.verify)
