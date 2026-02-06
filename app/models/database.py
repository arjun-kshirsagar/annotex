"""SQLAlchemy ORM models."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class JobStatus(enum.StrEnum):
    """Status of an evaluation job."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Verdict(enum.StrEnum):
    """Verdict for an evaluated answer segment."""

    CORRECT = "correct"
    PARTIAL = "partial"
    INCORRECT = "incorrect"


class ModelAnswer(Base):
    """Versioned model answer for an exam."""

    __tablename__ = "model_answers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    exam_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    ocr_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    segments: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    evaluation_jobs: Mapped[list["EvaluationJob"]] = relationship(
        "EvaluationJob", back_populates="model_answer"
    )

    __table_args__ = (UniqueConstraint("exam_id", "version", name="uq_exam_version"),)


class EvaluationJob(Base):
    """Evaluation job for a student submission."""

    __tablename__ = "evaluation_jobs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    submission_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    exam_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    model_answer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("model_answers.id"), nullable=False
    )
    original_file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        Enum(
            JobStatus,
            native_enum=True,
            values_callable=lambda obj: [item.value for item in obj],
        ),
        default=JobStatus.QUEUED,
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    model_answer: Mapped["ModelAnswer"] = relationship(
        "ModelAnswer", back_populates="evaluation_jobs"
    )
    answer_segments: Mapped[list["AnswerSegment"]] = relationship(
        "AnswerSegment", back_populates="job", cascade="all, delete-orphan"
    )
    annotated_file: Mapped["AnnotatedFile | None"] = relationship(
        "AnnotatedFile", back_populates="job", uselist=False
    )


class AnswerSegment(Base):
    """Segmented answer for a specific question."""

    __tablename__ = "answer_segments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("evaluation_jobs.id"), nullable=False
    )
    question_number: Mapped[int] = mapped_column(Integer, nullable=False)
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False)
    bounding_box: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    job: Mapped["EvaluationJob"] = relationship("EvaluationJob", back_populates="answer_segments")
    evaluation_result: Mapped["EvaluationResult | None"] = relationship(
        "EvaluationResult", back_populates="segment", uselist=False
    )


class EvaluationResult(Base):
    """Evaluation result for an answer segment."""

    __tablename__ = "evaluation_results"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    segment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("answer_segments.id"),
        nullable=False,
        unique=True,
    )
    model_answer_reference: Mapped[str] = mapped_column(Text, nullable=False)
    similarity_score: Mapped[float] = mapped_column(Float, nullable=False)
    verdict: Mapped[Verdict] = mapped_column(
        Enum(
            Verdict,
            native_enum=True,
            values_callable=lambda obj: [item.value for item in obj],
        ),
        nullable=False,
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    segment: Mapped["AnswerSegment"] = relationship(
        "AnswerSegment", back_populates="evaluation_result"
    )


class AnnotatedFile(Base):
    """Annotated PDF file for a completed evaluation."""

    __tablename__ = "annotated_files"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("evaluation_jobs.id"),
        nullable=False,
        unique=True,
    )
    submission_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    exam_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    job: Mapped["EvaluationJob"] = relationship("EvaluationJob", back_populates="annotated_file")
