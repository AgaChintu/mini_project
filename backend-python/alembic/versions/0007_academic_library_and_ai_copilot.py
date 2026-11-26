"""0007 Academic Library resources and AI Copilot tables

Revision ID: 0007
Revises: 0006_semester_management
Create Date: 2026-11-25
"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    # ------------------------------------------------------------------ #
    # academic_resources — central table for library uploads by faculty   #
    # ------------------------------------------------------------------ #
    op.create_table(
        "academic_resources",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("subject_id", sa.Integer, sa.ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("teacher_id", sa.Integer, sa.ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False, index=True),
        # PRIMARY or ADDITIONAL — resolved from SubjectTeacherAssignment at upload time
        sa.Column("faculty_category", sa.String(20), nullable=False, default="PRIMARY"),
        # pdf / doc / docx / youtube
        sa.Column("resource_type", sa.String(20), nullable=False),
        # Supabase storage path or local fallback path (null for youtube)
        sa.Column("storage_path", sa.Text, nullable=True),
        sa.Column("original_filename", sa.String(300), nullable=True),
        sa.Column("file_size", sa.Integer, nullable=True),
        sa.Column("mime_type", sa.String(100), nullable=True),
        # YouTube fields
        sa.Column("youtube_url", sa.Text, nullable=True),
        sa.Column("youtube_video_id", sa.String(50), nullable=True),
        sa.Column("youtube_thumbnail", sa.Text, nullable=True),
        sa.Column("youtube_title", sa.String(500), nullable=True),
        # Additional-faculty importance flag
        sa.Column("is_important", sa.Boolean, nullable=False, server_default=sa.text("false")),
        # Soft-delete / status
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'active'")),
        sa.Column("deleted_at", sa.DateTime, nullable=True),
        # AI indexing status: pending / processing / completed / failed / na
        sa.Column("index_status", sa.String(20), nullable=False, server_default=sa.text("'na'")),
        sa.Column("index_error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, nullable=True),
    )

    # ------------------------------------------------------------------ #
    # doubt_clusters — master doubt cards created by AI                   #
    # ------------------------------------------------------------------ #
    op.create_table(
        "doubt_clusters",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("subject_id", sa.Integer, sa.ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("teacher_id", sa.Integer, sa.ForeignKey("teachers.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("cluster_title", sa.String(300), nullable=False),
        sa.Column("ai_summary", sa.Text, nullable=True),
        sa.Column("keywords", sa.Text, nullable=True),  # comma-separated
        sa.Column("topic", sa.String(200), nullable=True),
        # priority: high / medium / low
        sa.Column("ai_priority", sa.String(20), nullable=False, server_default=sa.text("'medium'")),
        sa.Column("teacher_priority", sa.String(20), nullable=True),
        sa.Column("priority_reason", sa.Text, nullable=True),
        # status: pending / in_progress / answer_drafted / resolved / reopened
        sa.Column("status", sa.String(30), nullable=False, server_default=sa.text("'pending'")),
        # AI-drafted answer (before teacher review)
        sa.Column("ai_draft_answer", sa.Text, nullable=True),
        sa.Column("ai_draft_sources", sa.Text, nullable=True),  # JSON list of source citations
        sa.Column("teacher_edited_answer", sa.Text, nullable=True),
        sa.Column("published_answer", sa.Text, nullable=True),
        sa.Column("published_at", sa.DateTime, nullable=True),
        sa.Column("published_by_teacher_id", sa.Integer, sa.ForeignKey("teachers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("doubt_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, nullable=True),
    )

    # ------------------------------------------------------------------ #
    # doubt_cluster_members — links individual doubts to master cards     #
    # ------------------------------------------------------------------ #
    op.create_table(
        "doubt_cluster_members",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("cluster_id", sa.Integer, sa.ForeignKey("doubt_clusters.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("doubt_id", sa.Integer, sa.ForeignKey("doubts.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("similarity_score", sa.Float, nullable=True),
        sa.Column("added_at", sa.DateTime, nullable=False, server_default=sa.text("now()")),
        sa.Column("added_by", sa.String(20), nullable=False, server_default=sa.text("'ai'")),  # 'ai' or 'teacher'
        sa.UniqueConstraint("cluster_id", "doubt_id", name="uq_cluster_doubt"),
    )


def downgrade():
    op.drop_table("doubt_cluster_members")
    op.drop_table("doubt_clusters")
    op.drop_table("academic_resources")
