"""Segmentation service tests."""
import pytest

from app.services.ocr_service import BoundingBox, OCRBlock, OCRPage, OCRResult
from app.services.segmentation_service import SegmentationService


class TestSegmentationService:
    """Test segmentation service."""

    @pytest.fixture
    def service(self):
        """Get segmentation service."""
        return SegmentationService()

    @pytest.fixture
    def sample_ocr_result(self):
        """Create sample OCR result with question markers."""
        blocks = [
            OCRBlock(
                text="Q1. What is photosynthesis?",
                bounding_box=BoundingBox(page=0, x=50, y=100, width=400, height=30),
            ),
            OCRBlock(
                text="Photosynthesis is the process by which plants convert sunlight into energy.",
                bounding_box=BoundingBox(page=0, x=50, y=140, width=400, height=60),
            ),
            OCRBlock(
                text="Q2. Explain cellular respiration.",
                bounding_box=BoundingBox(page=0, x=50, y=220, width=400, height=30),
            ),
            OCRBlock(
                text="Cellular respiration is how cells break down glucose to produce ATP.",
                bounding_box=BoundingBox(page=0, x=50, y=260, width=400, height=60),
            ),
        ]

        page = OCRPage(
            page_number=0,
            width=612,
            height=792,
            blocks=blocks,
        )

        return OCRResult(pages=[page])

    def test_segment_by_question(self, service, sample_ocr_result):
        """Test basic question segmentation."""
        segments = service.segment_by_question(sample_ocr_result)

        assert len(segments) == 2
        assert segments[0].question_number == 1
        assert segments[1].question_number == 2

    def test_segment_text_content(self, service, sample_ocr_result):
        """Test that segment text is correctly merged."""
        segments = service.segment_by_question(sample_ocr_result)

        assert "photosynthesis" in segments[0].text.lower()
        assert "cellular respiration" in segments[1].text.lower()

    def test_segment_bounding_boxes(self, service, sample_ocr_result):
        """Test that bounding boxes are merged correctly."""
        segments = service.segment_by_question(sample_ocr_result)

        # First segment should encompass Q1 and its answer
        bbox1 = segments[0].bounding_box
        assert bbox1.x == 50
        assert bbox1.y == 100
        assert bbox1.height > 60  # Should span multiple blocks

    def test_no_question_markers(self, service):
        """Test segmentation when no question markers are found."""
        blocks = [
            OCRBlock(
                text="This is some text without question markers.",
                bounding_box=BoundingBox(page=0, x=50, y=100, width=400, height=30),
            ),
        ]
        ocr_result = OCRResult(pages=[OCRPage(page_number=0, width=612, height=792, blocks=blocks)])

        segments = service.segment_by_question(ocr_result)

        # Should create single segment with all content
        assert len(segments) == 1
        assert segments[0].question_number == 1

    def test_various_question_formats(self, service):
        """Test that various question formats are recognized."""
        formats = [
            "Q1. Question text",
            "Q.1 Question text",
            "Question 1: What is this?",
            "Ques 1 Answer here",
            "1. First question",
            "1) Another format",
            "(1) Parentheses format",
        ]

        for fmt in formats:
            blocks = [
                OCRBlock(
                    text=fmt,
                    bounding_box=BoundingBox(page=0, x=50, y=100, width=400, height=30),
                ),
            ]
            ocr_result = OCRResult(pages=[OCRPage(page_number=0, width=612, height=792, blocks=blocks)])

            segments = service.segment_by_question(ocr_result)
            assert len(segments) >= 1, f"Failed to recognize format: {fmt}"

    def test_empty_ocr_result(self, service):
        """Test segmentation with empty OCR result."""
        ocr_result = OCRResult(pages=[])
        segments = service.segment_by_question(ocr_result)

        assert len(segments) == 0

    def test_extract_segments_dict(self, service, sample_ocr_result):
        """Test extracting segments as dictionary."""
        segments_dict = service.extract_segments_dict(sample_ocr_result)

        assert "1" in segments_dict
        assert "2" in segments_dict
        assert "text" in segments_dict["1"]
        assert "bounding_box" in segments_dict["1"]
