"""Background evaluation tasks."""

import uuid
from datetime import UTC, datetime

from celery import Task
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger, log_context, setup_logging
from app.models.database import (
    AnnotatedFile,
    AnswerSegment,
    EvaluationJob,
    EvaluationResult,
    JobStatus,
    ModelAnswer,
    Verdict,
)
from app.services.annotation_renderer import AnnotationRenderer, AnnotationSegment
from app.services.evaluation_engine import EvaluationEngine
from app.services.ocr_service import get_ocr_provider
from app.services.segmentation_service import SegmentationService
from app.services.storage_service import get_storage_backend
from app.workers.celery_app import celery_app

logger = get_logger(__name__)
settings = get_settings()


def get_sync_session() -> Session:
    """Get synchronous database session for Celery tasks."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    # Convert async URL to sync
    sync_url = settings.database_url.replace("+asyncpg", "")
    engine = create_engine(sync_url)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


class EvaluationTask(Task):
    """Base task class with shared resources."""

    _ocr = None
    _segmentation = None
    _evaluation_engine = None
    _annotation_renderer = None
    _storage = None

    @property
    def ocr(self):
        if self._ocr is None:
            self._ocr = get_ocr_provider()
        return self._ocr

    @property
    def segmentation(self):
        if self._segmentation is None:
            self._segmentation = SegmentationService()
        return self._segmentation

    @property
    def evaluation_engine(self):
        if self._evaluation_engine is None:
            self._evaluation_engine = EvaluationEngine()
        return self._evaluation_engine

    @property
    def annotation_renderer(self):
        if self._annotation_renderer is None:
            self._annotation_renderer = AnnotationRenderer()
        return self._annotation_renderer

    @property
    def storage(self):
        if self._storage is None:
            self._storage = get_storage_backend()
        return self._storage


@celery_app.task(bind=True, base=EvaluationTask, max_retries=3)
def process_evaluation_task(self, job_id: str) -> dict:
    """Process an evaluation job.

    Steps:
    1. Load job & model answer from DB
    2. OCR student answer sheet
    3. Segment answers by question
    4. For each segment:
        - Get corresponding model answer segment
        - Compute semantic similarity
        - Determine verdict
        - Save records
    5. Render annotations on PDF
    6. Save annotated file to storage
    7. Create AnnotatedFile record
    8. Update job status

    Args:
        job_id: UUID of the evaluation job

    Returns:
        Dictionary with job status and result summary
    """
    setup_logging()
    log_context(job_id=job_id, task_id=self.request.id)
    logger.info("Starting evaluation task")

    db = get_sync_session()
    job_uuid = uuid.UUID(job_id)

    try:
        # Step 1: Load job and model answer
        job = db.execute(
            select(EvaluationJob).where(EvaluationJob.id == job_uuid)
        ).scalar_one_or_none()

        if not job:
            logger.error("Job not found")
            return {"status": "error", "message": f"Job {job_id} not found"}

        # Update status to processing
        job.status = JobStatus.PROCESSING
        db.commit()

        model_answer = db.execute(
            select(ModelAnswer).where(ModelAnswer.id == job.model_answer_id)
        ).scalar_one()

        logger.info(
            "Loaded job and model answer",
            exam_id=job.exam_id,
            submission_id=job.submission_id,
        )

        # Step 2: OCR student answer sheet
        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            student_ocr_result = loop.run_until_complete(
                self.ocr.extract_text(job.original_file_path)
            )
        finally:
            loop.close()

        logger.info(
            "Completed OCR",
            page_count=len(student_ocr_result.pages),
            block_count=len(student_ocr_result.get_all_blocks()),
        )

        # Step 3: Segment student answers
        student_segments = self.segmentation.segment_by_question(student_ocr_result)

        # Get model answer segments
        model_segments = model_answer.segments or {}

        logger.info(
            "Segmented answers",
            student_segments=len(student_segments),
            model_segments=len(model_segments),
        )

        # Step 4: Evaluate each segment
        annotation_segments = []
        results_summary = {"correct": 0, "partial": 0, "incorrect": 0}

        for student_segment in student_segments:
            q_num = str(student_segment.question_number)
            model_segment_data = model_segments.get(q_num)

            # Create answer segment record
            answer_segment = AnswerSegment(
                id=uuid.uuid4(),
                job_id=job.id,
                question_number=student_segment.question_number,
                extracted_text=student_segment.text,
                bounding_box=student_segment.bounding_box.to_dict(),
            )
            db.add(answer_segment)
            db.flush()

            # Evaluate if model answer exists for this question
            if model_segment_data:
                model_text = model_segment_data.get("text", "")
                evaluation_score = self.evaluation_engine.evaluate_answer(
                    student_segment.text,
                    model_text,
                )

                # Map string verdict to enum
                verdict_map = {
                    "correct": Verdict.CORRECT,
                    "partial": Verdict.PARTIAL,
                    "incorrect": Verdict.INCORRECT,
                }
                verdict_enum = verdict_map[evaluation_score.verdict.value]

                # Create evaluation result record
                eval_result = EvaluationResult(
                    id=uuid.uuid4(),
                    segment_id=answer_segment.id,
                    model_answer_reference=model_text,
                    similarity_score=evaluation_score.similarity_score,
                    verdict=verdict_enum,
                    confidence=evaluation_score.confidence,
                )
                db.add(eval_result)

                results_summary[evaluation_score.verdict.value] += 1

                # Add to annotation list
                annotation_segments.append(
                    AnnotationSegment(
                        bounding_box=student_segment.bounding_box,
                        verdict=evaluation_score.verdict,
                        question_number=student_segment.question_number,
                    )
                )
            else:
                logger.warning(
                    "No model answer for question",
                    question_number=student_segment.question_number,
                )

        db.commit()

        logger.info(
            "Completed evaluation",
            results=results_summary,
        )

        # Step 5: Render annotations
        annotated_pdf = self.annotation_renderer.render_annotations(
            job.original_file_path,
            annotation_segments,
        )

        # Step 6: Save annotated file
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            annotated_path = loop.run_until_complete(
                self.storage.save_bytes(
                    data=annotated_pdf,
                    exam_id=job.exam_id,
                    submission_id=job.submission_id,
                    filename="annotated.pdf",
                )
            )
        finally:
            loop.close()

        checksum = self.storage.compute_checksum(annotated_pdf)

        # Step 7: Create AnnotatedFile record
        annotated_file = AnnotatedFile(
            id=uuid.uuid4(),
            job_id=job.id,
            submission_id=job.submission_id,
            exam_id=job.exam_id,
            file_path=annotated_path,
            checksum=checksum,
        )
        db.add(annotated_file)

        # Step 8: Update job status
        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.now(tz=UTC)
        db.commit()

        logger.info(
            "Completed evaluation task",
            annotated_file_id=str(annotated_file.id),
            results=results_summary,
        )

        return {
            "status": "completed",
            "job_id": job_id,
            "results": results_summary,
            "annotated_file_id": str(annotated_file.id),
        }

    except Exception as e:
        logger.exception("Evaluation task failed", error=str(e))

        # Update job status to failed
        try:
            job = db.execute(
                select(EvaluationJob).where(EvaluationJob.id == job_uuid)
            ).scalar_one_or_none()
            if job:
                job.status = JobStatus.FAILED
                job.error_message = str(e)
                db.commit()
        except Exception:
            db.rollback()

        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=30 * (2**self.request.retries)) from e

    finally:
        db.close()
