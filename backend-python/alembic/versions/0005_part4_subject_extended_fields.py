"""Part 4: Add extended metadata fields to subjects table (department, semester_label, academic_year_label, is_active, timestamps)

Revision ID: 0005_part4_subject_extended
Revises: 0004_admin_and_subject_assignments
Create Date: 2026-11-25
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_part4_subject_extended"
down_revision = "0004_admin_and_assignments"
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns to subjects — all nullable or with defaults so existing data is preserved
    with op.batch_alter_table("subjects") as batch_op:
        batch_op.add_column(sa.Column("department", sa.String(100), nullable=True))
        batch_op.add_column(sa.Column("semester_label", sa.String(50), nullable=True))
        batch_op.add_column(sa.Column("academic_year_label", sa.String(50), nullable=True))
        batch_op.add_column(sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch_op.add_column(sa.Column("created_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("updated_at", sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table("subjects") as batch_op:
        batch_op.drop_column("updated_at")
        batch_op.drop_column("created_at")
        batch_op.drop_column("is_active")
        batch_op.drop_column("academic_year_label")
        batch_op.drop_column("semester_label")
        batch_op.drop_column("department")
