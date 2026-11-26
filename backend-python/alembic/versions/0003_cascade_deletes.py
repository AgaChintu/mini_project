"""Part 2: Add ON DELETE CASCADE to student and doubt dependent foreign keys

Revision ID: 0003_cascade
Revises: 0002_part2
Create Date: 2026-11-24 22:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0003_cascade'
down_revision: Union[str, None] = '0002_part2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. doubts.student_id -> students.id ON DELETE CASCADE
    op.drop_constraint('doubts_student_id_fkey', 'doubts', type_='foreignkey')
    op.create_foreign_key(
        'doubts_student_id_fkey',
        'doubts',
        'students',
        ['student_id'],
        ['id'],
        ondelete='CASCADE'
    )

    # 2. doubt_answers.doubt_id -> doubts.id ON DELETE CASCADE
    op.drop_constraint('doubt_answers_doubt_id_fkey', 'doubt_answers', type_='foreignkey')
    op.create_foreign_key(
        'doubt_answers_doubt_id_fkey',
        'doubt_answers',
        'doubts',
        ['doubt_id'],
        ['id'],
        ondelete='CASCADE'
    )

    # 3. attachments.doubt_id -> doubts.id ON DELETE CASCADE
    op.drop_constraint('attachments_doubt_id_fkey', 'attachments', type_='foreignkey')
    op.create_foreign_key(
        'attachments_doubt_id_fkey',
        'attachments',
        'doubts',
        ['doubt_id'],
        ['id'],
        ondelete='CASCADE'
    )

    # 4. saved_entries.student_id -> students.id ON DELETE CASCADE
    op.drop_constraint('saved_entries_student_id_fkey', 'saved_entries', type_='foreignkey')
    op.create_foreign_key(
        'saved_entries_student_id_fkey',
        'saved_entries',
        'students',
        ['student_id'],
        ['id'],
        ondelete='CASCADE'
    )

    # 5. session_doubts.student_id -> students.id ON DELETE CASCADE
    op.drop_constraint('session_doubts_student_id_fkey', 'session_doubts', type_='foreignkey')
    op.create_foreign_key(
        'session_doubts_student_id_fkey',
        'session_doubts',
        'students',
        ['student_id'],
        ['id'],
        ondelete='CASCADE'
    )


def downgrade() -> None:
    op.drop_constraint('session_doubts_student_id_fkey', 'session_doubts', type_='foreignkey')
    op.create_foreign_key(
        'session_doubts_student_id_fkey',
        'session_doubts',
        'students',
        ['student_id'],
        ['id']
    )

    op.drop_constraint('saved_entries_student_id_fkey', 'saved_entries', type_='foreignkey')
    op.create_foreign_key(
        'saved_entries_student_id_fkey',
        'saved_entries',
        'students',
        ['student_id'],
        ['id']
    )

    op.drop_constraint('attachments_doubt_id_fkey', 'attachments', type_='foreignkey')
    op.create_foreign_key(
        'attachments_doubt_id_fkey',
        'attachments',
        'doubts',
        ['doubt_id'],
        ['id']
    )

    op.drop_constraint('doubt_answers_doubt_id_fkey', 'doubt_answers', type_='foreignkey')
    op.create_foreign_key(
        'doubt_answers_doubt_id_fkey',
        'doubt_answers',
        'doubts',
        ['doubt_id'],
        ['id']
    )

    op.drop_constraint('doubts_student_id_fkey', 'doubts', type_='foreignkey')
    op.create_foreign_key(
        'doubts_student_id_fkey',
        'doubts',
        'students',
        ['student_id'],
        ['id']
    )
