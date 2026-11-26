"""Initial database foundation

Revision ID: 0001_initial
Revises: None
Create Date: 2026-11-24 14:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. academic_years
    op.create_table(
        'academic_years',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('year_number', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
        sa.UniqueConstraint('year_number')
    )
    op.create_index(op.f('ix_academic_years_id'), 'academic_years', ['id'], unique=False)

    # 2. semesters
    op.create_table(
        'semesters',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('academic_year_id', sa.Integer(), nullable=False),
        sa.Column('semester_number', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(['academic_year_id'], ['academic_years.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('academic_year_id', 'semester_number', name='uq_year_semester')
    )
    op.create_index(op.f('ix_semesters_id'), 'semesters', ['id'], unique=False)

    # 3. section_groups
    op.create_table(
        'section_groups',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('academic_year_id', sa.Integer(), nullable=False),
        sa.Column('semester_id', sa.Integer(), nullable=True),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['academic_year_id'], ['academic_years.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['semester_id'], ['semesters.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code')
    )
    op.create_index(op.f('ix_section_groups_id'), 'section_groups', ['id'], unique=False)

    # 4. sections
    op.create_table(
        'sections',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('academic_year_id', sa.Integer(), nullable=False),
        sa.Column('semester_id', sa.Integer(), nullable=True),
        sa.Column('code', sa.String(length=30), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.ForeignKeyConstraint(['academic_year_id'], ['academic_years.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['semester_id'], ['semesters.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('academic_year_id', 'code', name='uq_year_section')
    )
    op.create_index(op.f('ix_sections_id'), 'sections', ['id'], unique=False)

    # 5. section_group_members
    op.create_table(
        'section_group_members',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('section_group_id', sa.Integer(), nullable=False),
        sa.Column('section_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['section_group_id'], ['section_groups.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['section_id'], ['sections.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('section_group_id', 'section_id', name='uq_group_section')
    )
    op.create_index(op.f('ix_section_group_members_id'), 'section_group_members', ['id'], unique=False)

    # 6. subjects
    op.create_table(
        'subjects',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=30), nullable=True),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('subject_type', sa.String(length=30), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code')
    )
    op.create_index(op.f('ix_subjects_id'), 'subjects', ['id'], unique=False)

    # 7. subject_offerings
    op.create_table(
        'subject_offerings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('semester_id', sa.Integer(), nullable=False),
        sa.Column('section_group_id', sa.Integer(), nullable=False),
        sa.Column('subject_id', sa.Integer(), nullable=False),
        sa.Column('lecture_hours', sa.Integer(), nullable=True),
        sa.Column('tutorial_hours', sa.Integer(), nullable=True),
        sa.Column('practical_hours', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['section_group_id'], ['section_groups.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['semester_id'], ['semesters.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('semester_id', 'section_group_id', 'subject_id', name='uq_subject_offering')
    )
    op.create_index(op.f('ix_subject_offerings_id'), 'subject_offerings', ['id'], unique=False)

    # 8. syllabus_units
    op.create_table(
        'syllabus_units',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('subject_id', sa.Integer(), nullable=False),
        sa.Column('unit_number', sa.Integer(), nullable=False),
        sa.Column('unit_name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('proposed_lectures', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('subject_id', 'unit_number', name='uq_subject_unit')
    )
    op.create_index(op.f('ix_syllabus_units_id'), 'syllabus_units', ['id'], unique=False)

    # 9. syllabus_topics
    op.create_table(
        'syllabus_topics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('unit_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='1'),
        sa.ForeignKeyConstraint(['unit_id'], ['syllabus_units.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_syllabus_topics_id'), 'syllabus_topics', ['id'], unique=False)

    # 10. syllabus_subtopics
    op.create_table(
        'syllabus_subtopics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('topic_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='1'),
        sa.ForeignKeyConstraint(['topic_id'], ['syllabus_topics.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_syllabus_subtopics_id'), 'syllabus_subtopics', ['id'], unique=False)

    # 11. course_outcomes
    op.create_table(
        'course_outcomes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('subject_id', sa.Integer(), nullable=False),
        sa.Column('co_number', sa.Integer(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('bloom_levels', sa.String(length=50), nullable=True),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('subject_id', 'co_number', name='uq_subject_co')
    )
    op.create_index(op.f('ix_course_outcomes_id'), 'course_outcomes', ['id'], unique=False)

    # 12. textbooks
    op.create_table(
        'textbooks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('subject_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('authors', sa.String(length=500), nullable=True),
        sa.Column('publisher', sa.String(length=255), nullable=True),
        sa.Column('edition', sa.String(length=100), nullable=True),
        sa.Column('book_type', sa.String(length=30), nullable=True),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='1'),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_textbooks_id'), 'textbooks', ['id'], unique=False)

    # 13. teachers
    op.create_table(
        'teachers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('teacher_code', sa.String(length=50), nullable=False),
        sa.Column('full_name', sa.String(length=150), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('password_hash', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('teacher_code')
    )
    op.create_index(op.f('ix_teachers_id'), 'teachers', ['id'], unique=False)

    # 14. students
    op.create_table(
        'students',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('student_code', sa.String(length=50), nullable=False),
        sa.Column('full_name', sa.String(length=150), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('password_hash', sa.String(length=255), nullable=True),
        sa.Column('section_id', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['section_id'], ['sections.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('student_code')
    )
    op.create_index(op.f('ix_students_id'), 'students', ['id'], unique=False)

    # 15. teacher_assignments
    op.create_table(
        'teacher_assignments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('teacher_id', sa.Integer(), nullable=False),
        sa.Column('semester_id', sa.Integer(), nullable=False),
        sa.Column('section_id', sa.Integer(), nullable=False),
        sa.Column('subject_id', sa.Integer(), nullable=False),
        sa.Column('assignment_type', sa.String(length=50), nullable=True, server_default='primary'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['section_id'], ['sections.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['semester_id'], ['semesters.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['teacher_id'], ['teachers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('teacher_id', 'semester_id', 'section_id', 'subject_id', name='uq_teacher_semester_section_subject')
    )
    op.create_index(op.f('ix_teacher_assignments_id'), 'teacher_assignments', ['id'], unique=False)

    # 16. doubts
    op.create_table(
        'doubts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('doubt_code', sa.String(length=36), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('section_id', sa.Integer(), nullable=False),
        sa.Column('subject_id', sa.Integer(), nullable=False),
        sa.Column('teacher_id', sa.Integer(), nullable=True),
        sa.Column('topic_id', sa.Integer(), nullable=True),
        sa.Column('subtopic_id', sa.Integer(), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='pending'),
        sa.Column('is_anonymous_to_teacher', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['section_id'], ['sections.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['subtopic_id'], ['syllabus_subtopics.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['teacher_id'], ['teachers.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['topic_id'], ['syllabus_topics.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('doubt_code')
    )
    op.create_index(op.f('ix_doubts_id'), 'doubts', ['id'], unique=False)
    op.create_index(op.f('ix_doubts_status'), 'doubts', ['status'], unique=False)

    # 17. doubt_subtopics
    op.create_table(
        'doubt_subtopics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('doubt_id', sa.Integer(), nullable=False),
        sa.Column('subtopic_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['doubt_id'], ['doubts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['subtopic_id'], ['syllabus_subtopics.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('doubt_id', 'subtopic_id', name='uq_doubt_subtopic')
    )
    op.create_index(op.f('ix_doubt_subtopics_id'), 'doubt_subtopics', ['id'], unique=False)

    # 18. doubt_answers
    op.create_table(
        'doubt_answers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('doubt_id', sa.Integer(), nullable=False),
        sa.Column('teacher_id', sa.Integer(), nullable=False),
        sa.Column('answer_text', sa.Text(), nullable=False),
        sa.Column('resource_url', sa.String(length=1000), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['doubt_id'], ['doubts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['teacher_id'], ['teachers.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_doubt_answers_id'), 'doubt_answers', ['id'], unique=False)

    # 19. attachments
    op.create_table(
        'attachments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('doubt_id', sa.Integer(), nullable=False),
        sa.Column('original_filename', sa.String(length=255), nullable=False),
        sa.Column('stored_filename', sa.String(length=255), nullable=False),
        sa.Column('mime_type', sa.String(length=100), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('storage_path', sa.String(length=1000), nullable=False),
        sa.Column('uploaded_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['doubt_id'], ['doubts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stored_filename')
    )
    op.create_index(op.f('ix_attachments_id'), 'attachments', ['id'], unique=False)

    # 20. library_entries
    op.create_table(
        'library_entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('doubt_id', sa.Integer(), nullable=False),
        sa.Column('published_by_teacher_id', sa.Integer(), nullable=False),
        sa.Column('published_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['doubt_id'], ['doubts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['published_by_teacher_id'], ['teachers.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('doubt_id')
    )
    op.create_index(op.f('ix_library_entries_id'), 'library_entries', ['id'], unique=False)

    # 21. saved_entries
    op.create_table(
        'saved_entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('library_entry_id', sa.Integer(), nullable=False),
        sa.Column('saved_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['library_entry_id'], ['library_entries.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('student_id', 'library_entry_id', name='uq_student_saved_entry')
    )
    op.create_index(op.f('ix_saved_entries_id'), 'saved_entries', ['id'], unique=False)

    # 22. doubt_sessions
    op.create_table(
        'doubt_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('teacher_id', sa.Integer(), nullable=False),
        sa.Column('section_id', sa.Integer(), nullable=False),
        sa.Column('subject_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('session_date', sa.DateTime(), nullable=True),
        sa.Column('starts_at', sa.DateTime(), nullable=True),
        sa.Column('ends_at', sa.DateTime(), nullable=True),
        sa.Column('submission_opens_at', sa.DateTime(), nullable=False),
        sa.Column('submission_closes_at', sa.DateTime(), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='upcoming'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['section_id'], ['sections.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['teacher_id'], ['teachers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_doubt_sessions_id'), 'doubt_sessions', ['id'], unique=False)
    op.create_index(op.f('ix_doubt_sessions_status'), 'doubt_sessions', ['status'], unique=False)

    # 23. session_topics
    op.create_table(
        'session_topics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('topic_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['doubt_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['topic_id'], ['syllabus_topics.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_id', 'topic_id', name='uq_session_topic')
    )
    op.create_index(op.f('ix_session_topics_id'), 'session_topics', ['id'], unique=False)

    # 24. session_doubts
    op.create_table(
        'session_doubts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('topic_id', sa.Integer(), nullable=False),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('is_edited', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.ForeignKeyConstraint(['session_id'], ['doubt_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['topic_id'], ['syllabus_topics.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_session_doubts_id'), 'session_doubts', ['id'], unique=False)


def downgrade() -> None:
    op.drop_table('session_doubts')
    op.drop_table('session_topics')
    op.drop_table('doubt_sessions')
    op.drop_table('saved_entries')
    op.drop_table('library_entries')
    op.drop_table('attachments')
    op.drop_table('doubt_answers')
    op.drop_table('doubt_subtopics')
    op.drop_table('doubts')
    op.drop_table('teacher_assignments')
    op.drop_table('students')
    op.drop_table('teachers')
    op.drop_table('textbooks')
    op.drop_table('course_outcomes')
    op.drop_table('syllabus_subtopics')
    op.drop_table('syllabus_topics')
    op.drop_table('syllabus_units')
    op.drop_table('subject_offerings')
    op.drop_table('subjects')
    op.drop_table('section_group_members')
    op.drop_table('sections')
    op.drop_table('section_groups')
    op.drop_table('semesters')
    op.drop_table('academic_years')
