"""Model answer CRUD endpoints."""
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_ocr, get_segmentation_service, get_storage
from app.core.logging import get_logger
from app.models.database import ModelAnswer
from app.schemas.schemas import ModelAnswerCreate, ModelAnswerListResponse, ModelAnswerResponse
from app.services.ocr_service import OCRProvider
from app.services.segmentation_service import SegmentationService
from app.services.storage_service import StorageBackend

logger = get_logger(__name__)
router = APIRouter()


@router.post("/model-answers", response_model=ModelAnswerResponse, status_code=status.HTTP_201_CREATED)
async def create_model_answer(
    exam_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
    ocr: OCRProvider = Depends(get_ocr),
    segmentation: SegmentationService = Depends(get_segmentation_service),
) -> ModelAnswer:
    """Upload a new model answer PDF.

    Creates a new version for the exam. Does not activate it automatically.
    """
    # Validate file type
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are accepted",
        )

    # Get next version number
    result = await db.execute(
        select(ModelAnswer)
        .where(ModelAnswer.exam_id == exam_id)
        .order_by(ModelAnswer.version.desc())
        .limit(1)
    )
    existing = result.scalar_one_or_none()
    next_version = (existing.version + 1) if existing else 1

    # Save file to storage
    model_answer_id = uuid.uuid4()
    filename = f"model_answer_v{next_version}.pdf"
    file_content = await file.read()

    file_path = await storage.save_bytes(
        data=file_content,
        exam_id=exam_id,
        submission_id="model_answers",
        filename=filename,
    )

    # Perform OCR
    ocr_result = await ocr.extract_text_from_bytes(file_content, file.filename)
    ocr_data = ocr_result.to_dict()

    # Segment by questions
    segments = segmentation.extract_segments_dict(ocr_result)

    # Create database record
    model_answer = ModelAnswer(
        id=model_answer_id,
        exam_id=exam_id,
        version=next_version,
        file_path=file_path,
        ocr_data=ocr_data,
        segments=segments,
        is_active=False,
    )

    db.add(model_answer)
    await db.flush()

    logger.info(
        "Created model answer",
        model_answer_id=str(model_answer_id),
        exam_id=exam_id,
        version=next_version,
    )

    return model_answer


@router.get("/model-answers/{model_answer_id}", response_model=ModelAnswerResponse)
async def get_model_answer(
    model_answer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ModelAnswer:
    """Get model answer metadata by ID."""
    result = await db.execute(
        select(ModelAnswer).where(ModelAnswer.id == model_answer_id)
    )
    model_answer = result.scalar_one_or_none()

    if not model_answer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model answer {model_answer_id} not found",
        )

    return model_answer


@router.get("/exams/{exam_id}/model-answers", response_model=ModelAnswerListResponse)
async def list_model_answers_for_exam(
    exam_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List all model answer versions for an exam."""
    result = await db.execute(
        select(ModelAnswer)
        .where(ModelAnswer.exam_id == exam_id)
        .order_by(ModelAnswer.version.desc())
    )
    model_answers = result.scalars().all()

    return {
        "items": list(model_answers),
        "total": len(model_answers),
    }


@router.post("/model-answers/{model_answer_id}/activate", response_model=ModelAnswerResponse)
async def activate_model_answer(
    model_answer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ModelAnswer:
    """Activate a model answer version.

    Deactivates any currently active version for the same exam.
    """
    # Get the model answer
    result = await db.execute(
        select(ModelAnswer).where(ModelAnswer.id == model_answer_id)
    )
    model_answer = result.scalar_one_or_none()

    if not model_answer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model answer {model_answer_id} not found",
        )

    # Deactivate any existing active version for this exam
    result = await db.execute(
        select(ModelAnswer)
        .where(ModelAnswer.exam_id == model_answer.exam_id)
        .where(ModelAnswer.is_active == True)
    )
    active_answers = result.scalars().all()

    for active in active_answers:
        active.is_active = False

    # Activate this version
    model_answer.is_active = True
    await db.flush()

    logger.info(
        "Activated model answer",
        model_answer_id=str(model_answer_id),
        exam_id=model_answer.exam_id,
        version=model_answer.version,
    )

    return model_answer


@router.get("/exams/{exam_id}/active-model-answer", response_model=ModelAnswerResponse)
async def get_active_model_answer(
    exam_id: str,
    db: AsyncSession = Depends(get_db),
) -> ModelAnswer:
    """Get the currently active model answer for an exam."""
    result = await db.execute(
        select(ModelAnswer)
        .where(ModelAnswer.exam_id == exam_id)
        .where(ModelAnswer.is_active == True)
    )
    model_answer = result.scalar_one_or_none()

    if not model_answer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active model answer found for exam {exam_id}",
        )

    return model_answer
