"""Part 2: Dashboard and dynamic registration schema additions

Revision ID: 0002_part2
Revises: 0001_initial
Create Date: 2026-11-24 16:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0002_part2'
down_revision: Union[str, None] = '0001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Student columns
    op.add_column('students', sa.Column('department', sa.String(length=100), nullable=True))

    # Teacher columns
    op.add_column('teachers', sa.Column('department', sa.String(length=100), nullable=True))
    op.add_column('teachers', sa.Column('designation', sa.String(length=100), nullable=True))
    op.add_column('teachers', sa.Column('profile_info', sa.String(length=500), nullable=True))

    # Doubt columns
    op.add_column('doubts', sa.Column('ai_summary', sa.Text(), nullable=True))
    op.add_column('doubts', sa.Column('keywords', sa.String(length=500), nullable=True))
    op.add_column('doubts', sa.Column('cluster_title', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('doubts', 'cluster_title')
    op.drop_column('doubts', 'keywords')
    op.drop_column('doubts', 'ai_summary')

    op.drop_column('teachers', 'profile_info')
    op.drop_column('teachers', 'designation')
    op.drop_column('teachers', 'department')

    op.drop_column('students', 'department')
