"""Dependency injection for API routes."""

from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.services.annotation_renderer import AnnotationRenderer
from app.services.evaluation_engine import EvaluationEngine
from app.services.ocr_service import OCRProvider, get_ocr_provider
from app.services.segmentation_service import SegmentationService
from app.services.storage_service import StorageBackend, get_storage_backend


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that provides a database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@lru_cache
def get_storage() -> StorageBackend:
    """Get cached storage backend instance."""
    return get_storage_backend()


@lru_cache
def get_ocr() -> OCRProvider:
    """Get cached OCR provider instance."""
    return get_ocr_provider()


@lru_cache
def get_segmentation_service() -> SegmentationService:
    """Get cached segmentation service instance."""
    return SegmentationService()


@lru_cache
def get_evaluation_engine() -> EvaluationEngine:
    """Get cached evaluation engine instance."""
    return EvaluationEngine()


@lru_cache
def get_annotation_renderer() -> AnnotationRenderer:
    """Get cached annotation renderer instance."""
    return AnnotationRenderer()
