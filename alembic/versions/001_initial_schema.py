"""Initial schema with all tables.

Revision ID: 001
Revises:
Create Date: 2025-01-17

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create job_status enum
    job_status_enum = postgresql.ENUM(
        "queued", "processing", "completed", "failed",
        name="jobstatus",
        create_type=False,
    )
    job_status_enum.create(op.get_bind(), checkfirst=True)

    # Create verdict enum
    verdict_enum = postgresql.ENUM(
        "correct", "partial", "incorrect",
        name="verdict",
        create_type=False,
    )
    verdict_enum.create(op.get_bind(), checkfirst=True)

    # Create model_answers table
    op.create_table(
        "model_answers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("exam_id", sa.String(255), nullable=False, index=True),
        sa.Column("version", sa.Integer(), nullable=False, default=1),
        sa.Column("file_path", sa.String(1024), nullable=False),
        sa.Column("ocr_data", postgresql.JSONB(), nullable=True),
        sa.Column("segments", postgresql.JSONB(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("exam_id", "version", name="uq_exam_version"),
    )

    # Create evaluation_jobs table
    op.create_table(
        "evaluation_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "submission_id", sa.String(255), nullable=False, unique=True, index=True
        ),
        sa.Column("exam_id", sa.String(255), nullable=False, index=True),
        sa.Column(
            "model_answer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("model_answers.id"),
            nullable=False,
        ),
        sa.Column("original_file_path", sa.String(1024), nullable=False),
        sa.Column(
            "status",
            job_status_enum,
            nullable=False,
            server_default="queued",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Create answer_segments table
    op.create_table(
        "answer_segments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("evaluation_jobs.id"),
            nullable=False,
        ),
        sa.Column("question_number", sa.Integer(), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=False),
        sa.Column("bounding_box", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Create evaluation_results table
    op.create_table(
        "evaluation_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "segment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("answer_segments.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("model_answer_reference", sa.Text(), nullable=False),
        sa.Column("similarity_score", sa.Float(), nullable=False),
        sa.Column("verdict", verdict_enum, nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Create annotated_files table
    op.create_table(
        "annotated_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("evaluation_jobs.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("submission_id", sa.String(255), nullable=False, index=True),
        sa.Column("exam_id", sa.String(255), nullable=False, index=True),
        sa.Column("file_path", sa.String(1024), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("annotated_files")
    op.drop_table("evaluation_results")
    op.drop_table("answer_segments")
    op.drop_table("evaluation_jobs")
    op.drop_table("model_answers")

    # Drop enums
    op.execute("DROP TYPE IF EXISTS verdict")
    op.execute("DROP TYPE IF EXISTS jobstatus")
