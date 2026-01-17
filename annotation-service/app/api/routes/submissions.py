"""Submission-related endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_storage
from app.core.logging import get_logger
from app.models.database import AnnotatedFile
from app.schemas.schemas import AnnotatedFileResponse
from app.services.storage_service import StorageBackend

logger = get_logger(__name__)
router = APIRouter()


@router.get(
    "/submissions/{submission_id}/annotated-sheet",
    response_class=Response,
    responses={
        200: {
            "content": {"application/pdf": {}},
            "description": "Annotated PDF file",
        },
        404: {"description": "Annotated sheet not found"},
    },
)
async def download_annotated_sheet(
    submission_id: str,
    db: AsyncSession = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
) -> Response:
    """Download the annotated PDF for a submission."""
    # Find annotated file
    result = await db.execute(
        select(AnnotatedFile).where(AnnotatedFile.submission_id == submission_id)
    )
    annotated_file = result.scalar_one_or_none()

    if not annotated_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Annotated sheet not found for submission {submission_id}",
        )

    # Get file from storage
    try:
        file_content = await storage.get(annotated_file.file_path)
    except FileNotFoundError:
        logger.error(
            "Annotated file missing from storage",
            submission_id=submission_id,
            file_path=annotated_file.file_path,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Annotated file not found in storage",
        )

    # Verify checksum
    computed_checksum = storage.compute_checksum(file_content)
    if computed_checksum != annotated_file.checksum:
        logger.error(
            "Annotated file checksum mismatch",
            submission_id=submission_id,
            expected=annotated_file.checksum,
            computed=computed_checksum,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="File integrity check failed",
        )

    return Response(
        content=file_content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="annotated_{submission_id}.pdf"',
            "X-Checksum": annotated_file.checksum,
        },
    )


@router.get(
    "/submissions/{submission_id}/annotated-sheet/metadata",
    response_model=AnnotatedFileResponse,
)
async def get_annotated_sheet_metadata(
    submission_id: str,
    db: AsyncSession = Depends(get_db),
) -> AnnotatedFile:
    """Get metadata for the annotated sheet."""
    result = await db.execute(
        select(AnnotatedFile).where(AnnotatedFile.submission_id == submission_id)
    )
    annotated_file = result.scalar_one_or_none()

    if not annotated_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Annotated sheet not found for submission {submission_id}",
        )

    return annotated_file
