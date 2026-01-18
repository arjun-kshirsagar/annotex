"""Question segmentation logic using keyword detection."""
import re
from dataclasses import dataclass, field

from app.core.logging import get_logger
from app.services.ocr_service import BoundingBox, OCRBlock, OCRResult

logger = get_logger(__name__)

# Question boundary detection patterns
QUESTION_PATTERNS = [
    # Q1, Q.1, Q 1, Q-1
    r"^Q\.?\s*-?\s*(\d+)",
    # Question 1, Ques 1, Ques. 1
    r"^(?:Question|Ques)\.?\s*(\d+)",
    # Ans 1, Answer 1, A1, A.1
    r"^(?:Ans(?:wer)?|A)\.?\s*(\d+)",
    # 1., 1), (1) at line start
    r"^\(?(\d+)\)?[.\)]\s",
]

# Compile patterns for efficiency
COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in QUESTION_PATTERNS]


@dataclass
class QuestionSegment:
    """A segmented question/answer with its text and location."""

    question_number: int
    text: str
    bounding_box: BoundingBox
    blocks: list[OCRBlock] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "question_number": self.question_number,
            "text": self.text,
            "bounding_box": self.bounding_box.to_dict(),
            "blocks": [b.to_dict() for b in self.blocks],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "QuestionSegment":
        """Create from dictionary."""
        return cls(
            question_number=data["question_number"],
            text=data["text"],
            bounding_box=BoundingBox.from_dict(data["bounding_box"]),
            blocks=[OCRBlock.from_dict(b) for b in data.get("blocks", [])],
        )


class SegmentationService:
    """Service for segmenting text into question/answer sections."""

    def __init__(self, patterns: list[re.Pattern] | None = None):
        """Initialize segmentation service.

        Args:
            patterns: Optional custom regex patterns for question detection
        """
        self.patterns = patterns or COMPILED_PATTERNS

    def segment_by_question(self, ocr_result: OCRResult) -> list[QuestionSegment]:
        """Segment OCR result into question sections.

        Algorithm:
        1. Collect all blocks across pages
        2. Scan for question boundary patterns
        3. Group consecutive blocks between boundaries
        4. Merge bounding boxes for each segment

        Args:
            ocr_result: OCR extraction result

        Returns:
            List of question segments with text and bounding boxes
        """
        all_blocks = ocr_result.get_all_blocks()
        if not all_blocks:
            logger.warning("No OCR blocks to segment")
            return []

        # Find question boundaries
        boundaries = self._find_question_boundaries(all_blocks)

        if not boundaries:
            # No question markers found, treat entire text as one segment
            logger.info("No question markers found, creating single segment")
            return [self._create_segment(1, all_blocks)]

        # Sort boundaries by position
        boundaries.sort(key=lambda b: (b["block_index"], b["question_number"]))

        # Group blocks between boundaries
        segments = []
        for i, boundary in enumerate(boundaries):
            start_idx = boundary["block_index"]
            end_idx = boundaries[i + 1]["block_index"] if i + 1 < len(boundaries) else len(all_blocks)

            segment_blocks = all_blocks[start_idx:end_idx]
            if segment_blocks:
                segment = self._create_segment(
                    boundary["question_number"],
                    segment_blocks,
                )
                segments.append(segment)

        logger.info(
            "Segmented OCR result",
            total_blocks=len(all_blocks),
            segment_count=len(segments),
            questions=[s.question_number for s in segments],
        )

        return segments

    def _find_question_boundaries(self, blocks: list[OCRBlock]) -> list[dict]:
        """Find question boundary markers in blocks.

        Args:
            blocks: List of OCR blocks

        Returns:
            List of boundary markers with block index and question number
        """
        boundaries = []

        for idx, block in enumerate(blocks):
            text = block.text.strip()
            for pattern in self.patterns:
                match = pattern.match(text)
                if match:
                    try:
                        question_num = int(match.group(1))
                        boundaries.append({
                            "block_index": idx,
                            "question_number": question_num,
                            "matched_text": match.group(0),
                        })
                        break
                    except (ValueError, IndexError):
                        continue

        return boundaries

    def _create_segment(
        self,
        question_number: int,
        blocks: list[OCRBlock],
    ) -> QuestionSegment:
        """Create a question segment from blocks.

        Args:
            question_number: Question number
            blocks: OCR blocks belonging to this segment

        Returns:
            Question segment with merged text and bounding box
        """
        # Merge text
        text = " ".join(block.text.strip() for block in blocks)

        # Merge bounding boxes
        merged_bbox = self._merge_bounding_boxes([b.bounding_box for b in blocks])

        return QuestionSegment(
            question_number=question_number,
            text=text,
            bounding_box=merged_bbox,
            blocks=blocks,
        )

    def _merge_bounding_boxes(self, boxes: list[BoundingBox]) -> BoundingBox:
        """Merge multiple bounding boxes into one encompassing box.

        Args:
            boxes: List of bounding boxes to merge

        Returns:
            Single bounding box encompassing all inputs
        """
        if not boxes:
            return BoundingBox(page=0, x=0, y=0, width=0, height=0)

        if len(boxes) == 1:
            return boxes[0]

        # Use the page from the first box
        page = boxes[0].page

        min_x = min(b.x for b in boxes)
        min_y = min(b.y for b in boxes)
        max_x = max(b.x + b.width for b in boxes)
        max_y = max(b.y + b.height for b in boxes)

        return BoundingBox(
            page=page,
            x=min_x,
            y=min_y,
            width=max_x - min_x,
            height=max_y - min_y,
        )

    def extract_segments_dict(self, ocr_result: OCRResult) -> dict:
        """Extract segments and return as dictionary.

        Args:
            ocr_result: OCR extraction result

        Returns:
            Dictionary with question numbers as keys and segment data as values
        """
        segments = self.segment_by_question(ocr_result)
        return {
            str(s.question_number): s.to_dict()
            for s in segments
        }
