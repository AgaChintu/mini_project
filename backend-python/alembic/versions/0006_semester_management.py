"""Part 5: Semester-based academic management (current_semester for students, semester_number for subjects)

Revision ID: 0006_semester_management
Revises: 0005_part4_subject_extended
Create Date: 2026-11-25
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_semester_management"
down_revision = "0005_part4_subject_extended"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Add current_semester to students table
    with op.batch_alter_table("students") as batch_op:
        batch_op.add_column(sa.Column("current_semester", sa.Integer(), nullable=True))
        batch_op.create_index("ix_students_current_semester", ["current_semester"], unique=False)

    # 2. Add semester_number to subjects table
    with op.batch_alter_table("subjects") as batch_op:
        batch_op.add_column(sa.Column("semester_number", sa.Integer(), nullable=True))
        batch_op.create_index("ix_subjects_semester_number", ["semester_number"], unique=False)

    # 3. Data backfill for existing records:
    # Backfill students from their section's semester if available
    op.execute("""
        UPDATE students s
        SET current_semester = sem.semester_number
        FROM sections sec
        JOIN semesters sem ON sec.semester_id = sem.id
        WHERE s.section_id = sec.id
          AND s.current_semester IS NULL
    """)

    # Backfill subjects:
    # Subjects with code starting with BAS1, BCO1 -> semester 1
    op.execute("""
        UPDATE subjects
        SET semester_number = 1,
            semester_label = 'Semester 1'
        WHERE (code LIKE 'BAS1%' OR code LIKE 'BCO1%' OR code LIKE '%101' OR code LIKE '%102' OR code LIKE '%103')
          AND semester_number IS NULL
    """)

    # Subjects with code starting with BCS3, BCC3, BAS3, BOE3 -> semester 3
    op.execute("""
        UPDATE subjects
        SET semester_number = 3,
            semester_label = 'Semester 3'
        WHERE (code LIKE 'BCS3%' OR code LIKE 'BCC3%' OR code LIKE 'BAS3%' OR code LIKE 'BOE3%' OR code LIKE '%301' OR code LIKE '%302' OR code LIKE '%303' OR code LIKE '%310')
          AND semester_number IS NULL
    """)


def downgrade():
    with op.batch_alter_table("subjects") as batch_op:
        batch_op.drop_index("ix_subjects_semester_number")
        batch_op.drop_column("semester_number")

    with op.batch_alter_table("students") as batch_op:
        batch_op.drop_index("ix_students_current_semester")
        batch_op.drop_column("current_semester")
