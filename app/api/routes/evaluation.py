"""Evaluation job endpoints."""

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db, get_storage
from app.core.logging import get_logger
from app.models.database import (
    AnswerSegment,
    EvaluationJob,
    JobStatus,
    ModelAnswer,
)
from app.schemas.schemas import (
    AnswerSegmentResponse,
    BoundingBox,
    EvaluationJobResponse,
    EvaluationResultResponse,
    JobResultsResponse,
    SegmentWithResult,
)
from app.services.storage_service import StorageBackend
from app.workers.tasks import process_evaluation_task

logger = get_logger(__name__)
router = APIRouter()


@router.post(
    "/evaluate", response_model=EvaluationJobResponse, status_code=status.HTTP_202_ACCEPTED
)
async def submit_evaluation(
    submission_id: str,
    exam_id: str,
    file: UploadFile = File(...),
    model_answer_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
) -> EvaluationJob:
    """Submit a student answer sheet for evaluation.

    Creates an evaluation job and queues it for background processing.
    Returns immediately with job ID for status polling.
    """
    # Validate file type
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are accepted",
        )

    # Check for duplicate submission
    result = await db.execute(
        select(EvaluationJob).where(EvaluationJob.submission_id == submission_id)
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Evaluation already exists for submission {submission_id}",
        )

    # Get model answer
    if model_answer_id:
        result = await db.execute(select(ModelAnswer).where(ModelAnswer.id == model_answer_id))
        model_answer = result.scalar_one_or_none()
        if not model_answer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model answer {model_answer_id} not found",
            )
    else:
        # Get active model answer for exam
        result = await db.execute(
            select(ModelAnswer)
            .where(ModelAnswer.exam_id == exam_id)
            .where(ModelAnswer.is_active.is_(True))
        )
        model_answer = result.scalar_one_or_none()
        if not model_answer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No active model answer found for exam {exam_id}",
            )

    # Save uploaded file
    file_content = await file.read()
    file_path = await storage.save_bytes(
        data=file_content,
        exam_id=exam_id,
        submission_id=submission_id,
        filename="submission.pdf",
    )

    # Create evaluation job
    job = EvaluationJob(
        id=uuid.uuid4(),
        submission_id=submission_id,
        exam_id=exam_id,
        model_answer_id=model_answer.id,
        original_file_path=file_path,
        status=JobStatus.QUEUED,
    )

    db.add(job)
    await db.flush()

    # Queue background task
    process_evaluation_task.delay(str(job.id))

    logger.info(
        "Submitted evaluation job",
        job_id=str(job.id),
        submission_id=submission_id,
        exam_id=exam_id,
    )

    return job


@router.get("/jobs/{job_id}", response_model=EvaluationJobResponse)
async def get_job_status(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> EvaluationJob:
    """Get evaluation job status."""
    result = await db.execute(select(EvaluationJob).where(EvaluationJob.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    return job


@router.get("/jobs/{job_id}/results", response_model=JobResultsResponse)
async def get_job_results(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get detailed evaluation results for a job."""
    result = await db.execute(
        select(EvaluationJob)
        .where(EvaluationJob.id == job_id)
        .options(
            selectinload(EvaluationJob.answer_segments).selectinload(
                AnswerSegment.evaluation_result
            )
        )
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job is not completed. Current status: {job.status.value}",
        )

    # Build response
    segments_with_results = []
    for segment in sorted(job.answer_segments, key=lambda s: s.question_number):
        segment_response = AnswerSegmentResponse(
            id=segment.id,
            question_number=segment.question_number,
            extracted_text=segment.extracted_text,
            bounding_box=BoundingBox(**segment.bounding_box),
            created_at=segment.created_at,
        )

        result_response = None
        if segment.evaluation_result:
            er = segment.evaluation_result
            result_response = EvaluationResultResponse(
                id=er.id,
                segment_id=er.segment_id,
                model_answer_reference=er.model_answer_reference,
                similarity_score=er.similarity_score,
                verdict=er.verdict.value,
                confidence=er.confidence,
                created_at=er.created_at,
            )

        segments_with_results.append(
            SegmentWithResult(segment=segment_response, result=result_response)
        )

    return {
        "job": job,
        "segments": segments_with_results,
    }
