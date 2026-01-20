"""Pydantic request/response schemas."""

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class Verdict(str, Enum):
    """Verdict for an evaluated answer segment."""

    CORRECT = "correct"
    PARTIAL = "partial"
    INCORRECT = "incorrect"


class JobStatus(str, Enum):
    """Status of an evaluation job."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# ==================== Bounding Box ====================


class BoundingBox(BaseModel):
    """Bounding box for text location on a page."""

    page: int = Field(..., ge=0, description="Page number (0-indexed)")
    x: float = Field(..., ge=0, description="X coordinate")
    y: float = Field(..., ge=0, description="Y coordinate")
    width: float = Field(..., gt=0, description="Width")
    height: float = Field(..., gt=0, description="Height")


# ==================== Model Answer ====================


class ModelAnswerCreate(BaseModel):
    """Request schema for creating a model answer."""

    exam_id: str = Field(..., min_length=1, max_length=255)


class ModelAnswerResponse(BaseModel):
    """Response schema for model answer."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    exam_id: str
    version: int
    file_path: str
    is_active: bool
    created_at: datetime
    segments: dict | None = None


class ModelAnswerListResponse(BaseModel):
    """Response schema for listing model answers."""

    items: list[ModelAnswerResponse]
    total: int


# ==================== Evaluation Job ====================


class EvaluationJobCreate(BaseModel):
    """Request schema for creating an evaluation job."""

    submission_id: str = Field(..., min_length=1, max_length=255)
    exam_id: str = Field(..., min_length=1, max_length=255)
    model_answer_id: uuid.UUID | None = Field(
        default=None,
        description="Optional model answer ID. If not provided, uses active model answer for exam.",
    )


class EvaluationJobResponse(BaseModel):
    """Response schema for evaluation job."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    submission_id: str
    exam_id: str
    model_answer_id: uuid.UUID
    status: JobStatus
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


# ==================== Answer Segment ====================


class AnswerSegmentResponse(BaseModel):
    """Response schema for answer segment."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    question_number: int
    extracted_text: str
    bounding_box: BoundingBox
    created_at: datetime


# ==================== Evaluation Result ====================


class EvaluationResultResponse(BaseModel):
    """Response schema for evaluation result."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    segment_id: uuid.UUID
    model_answer_reference: str
    similarity_score: float
    verdict: Verdict
    confidence: float
    created_at: datetime


class SegmentWithResult(BaseModel):
    """Combined segment and result response."""

    model_config = ConfigDict(from_attributes=True)

    segment: AnswerSegmentResponse
    result: EvaluationResultResponse | None = None


class JobResultsResponse(BaseModel):
    """Response schema for job results with all segments."""

    job: EvaluationJobResponse
    segments: list[SegmentWithResult]


# ==================== Annotated File ====================


class AnnotatedFileResponse(BaseModel):
    """Response schema for annotated file."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    submission_id: str
    exam_id: str
    file_path: str
    checksum: str
    created_at: datetime


# ==================== Error Responses ====================


class ErrorResponse(BaseModel):
    """Standard error response."""

    detail: str
    error_code: str | None = None


class ValidationErrorResponse(BaseModel):
    """Validation error response."""

    detail: list[dict]
