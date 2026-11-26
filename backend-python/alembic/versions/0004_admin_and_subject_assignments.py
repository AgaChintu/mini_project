"""Part 3: Admin model and Subject-Teacher Assignments

Revision ID: 0004_admin_and_assignments
Revises: 0003_cascade
Create Date: 2026-11-24 23:25:00.000000

"""
from typing import Sequence, Union
from datetime import datetime

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0004_admin_and_assignments'
down_revision: Union[str, None] = '0003_cascade'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    # 1. Create admins table if not exists
    if 'admins' not in tables:
        op.create_table(
            'admins',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('username', sa.String(length=50), nullable=False),
            sa.Column('full_name', sa.String(length=150), nullable=False),
            sa.Column('email', sa.String(length=255), nullable=False),
            sa.Column('password_hash', sa.String(length=255), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_admins_id'), 'admins', ['id'], unique=False)
        op.create_index(op.f('ix_admins_username'), 'admins', ['username'], unique=True)
        op.create_index(op.f('ix_admins_email'), 'admins', ['email'], unique=True)

    # 2. Create subject_teacher_assignments table if not exists
    if 'subject_teacher_assignments' not in tables:
        op.create_table(
            'subject_teacher_assignments',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('subject_id', sa.Integer(), nullable=False),
            sa.Column('teacher_id', sa.Integer(), nullable=False),
            sa.Column('is_primary', sa.Boolean(), nullable=False, server_default=sa.text('false')),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
            sa.Column('assigned_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
            sa.Column('assigned_by_admin_id', sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['teacher_id'], ['teachers.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['assigned_by_admin_id'], ['admins.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('subject_id', 'teacher_id', name='uq_subject_teacher_direct'),
        )
        op.create_index(op.f('ix_subject_teacher_assignments_id'), 'subject_teacher_assignments', ['id'], unique=False)
        op.create_index(op.f('ix_subject_teacher_assignments_subject_id'), 'subject_teacher_assignments', ['subject_id'], unique=False)
        op.create_index(op.f('ix_subject_teacher_assignments_teacher_id'), 'subject_teacher_assignments', ['teacher_id'], unique=False)

    # 3. Populate subject_teacher_assignments from existing teacher_assignments (idempotent)
    conn.execute(sa.text("""
        INSERT INTO subject_teacher_assignments (subject_id, teacher_id, is_primary, is_active, assigned_at)
        SELECT 
            subject_id, 
            teacher_id, 
            (ROW_NUMBER() OVER(PARTITION BY subject_id ORDER BY id ASC) = 1) AS is_primary,
            true AS is_active,
            NOW() AS assigned_at
        FROM (
            SELECT DISTINCT ON (subject_id, teacher_id) id, subject_id, teacher_id
            FROM teacher_assignments
            ORDER BY subject_id, teacher_id, id ASC
        ) distinct_assignments
        ON CONFLICT (subject_id, teacher_id) DO NOTHING;
    """))


def downgrade() -> None:
    pass
