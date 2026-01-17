"""Services module."""
from app.services.annotation_renderer import AnnotationRenderer
from app.services.evaluation_engine import EvaluationEngine
from app.services.ocr_service import GoogleVisionOCR, MockOCR, OCRProvider
from app.services.segmentation_service import SegmentationService
from app.services.storage_service import LocalStorage, StorageBackend

__all__ = [
    "StorageBackend",
    "LocalStorage",
    "OCRProvider",
    "GoogleVisionOCR",
    "MockOCR",
    "SegmentationService",
    "EvaluationEngine",
    "AnnotationRenderer",
]
