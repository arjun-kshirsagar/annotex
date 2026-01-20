"""PDF annotation rendering service."""

import io
from dataclasses import dataclass

import fitz  # PyMuPDF
from PIL import Image

from app.core.logging import get_logger
from app.services.evaluation_engine import Verdict
from app.services.ocr_service import BoundingBox

logger = get_logger(__name__)


# Colors for annotations (RGBA)
ANNOTATION_COLORS = {
    Verdict.CORRECT: (0, 200, 0, 100),  # Green with transparency
    Verdict.PARTIAL: (255, 200, 0, 100),  # Yellow with transparency
    Verdict.INCORRECT: (255, 0, 0, 100),  # Red with transparency
}

# Border colors (RGB)
BORDER_COLORS = {
    Verdict.CORRECT: (0, 150, 0),
    Verdict.PARTIAL: (200, 150, 0),
    Verdict.INCORRECT: (200, 0, 0),
}


@dataclass
class AnnotationSegment:
    """A segment to annotate with its verdict."""

    bounding_box: BoundingBox
    verdict: Verdict
    question_number: int


class AnnotationRenderer:
    """Service for rendering annotations on PDFs."""

    def __init__(self, dpi: int = 150):
        """Initialize annotation renderer.

        Args:
            dpi: DPI for PDF to image conversion
        """
        self.dpi = dpi
        self.scale = dpi / 72.0  # PDF points to pixels

    def render_annotations(
        self,
        pdf_path: str,
        segments: list[AnnotationSegment],
    ) -> bytes:
        """Render annotations on a PDF and return as bytes.

        Args:
            pdf_path: Path to the original PDF
            segments: List of segments with verdicts to annotate

        Returns:
            Annotated PDF as bytes
        """
        doc = fitz.open(pdf_path)

        try:
            # Group segments by page
            segments_by_page: dict[int, list[AnnotationSegment]] = {}
            for segment in segments:
                page_num = segment.bounding_box.page
                if page_num not in segments_by_page:
                    segments_by_page[page_num] = []
                segments_by_page[page_num].append(segment)

            # Process each page
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_segments = segments_by_page.get(page_num, [])

                if page_segments:
                    self._annotate_page(page, page_segments)

            # Save to bytes
            output = io.BytesIO()
            doc.save(output)
            output.seek(0)

            logger.info(
                "Rendered annotations on PDF",
                page_count=len(doc),
                annotation_count=len(segments),
            )

            return output.read()

        finally:
            doc.close()

    def render_annotations_from_bytes(
        self,
        pdf_data: bytes,
        segments: list[AnnotationSegment],
    ) -> bytes:
        """Render annotations on PDF data and return as bytes.

        Args:
            pdf_data: Original PDF as bytes
            segments: List of segments with verdicts to annotate

        Returns:
            Annotated PDF as bytes
        """
        doc = fitz.open(stream=pdf_data, filetype="pdf")

        try:
            # Group segments by page
            segments_by_page: dict[int, list[AnnotationSegment]] = {}
            for segment in segments:
                page_num = segment.bounding_box.page
                if page_num not in segments_by_page:
                    segments_by_page[page_num] = []
                segments_by_page[page_num].append(segment)

            # Process each page
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_segments = segments_by_page.get(page_num, [])

                if page_segments:
                    self._annotate_page(page, page_segments)

            # Save to bytes
            output = io.BytesIO()
            doc.save(output)
            output.seek(0)

            return output.read()

        finally:
            doc.close()

    def _annotate_page(
        self,
        page: fitz.Page,
        segments: list[AnnotationSegment],
    ) -> None:
        """Add annotations to a single page.

        Args:
            page: PyMuPDF page object
            segments: Segments to annotate on this page
        """
        for segment in segments:
            bbox = segment.bounding_box
            verdict = segment.verdict

            # Create rectangle for annotation
            rect = fitz.Rect(
                bbox.x,
                bbox.y,
                bbox.x + bbox.width,
                bbox.y + bbox.height,
            )

            # Get color based on verdict
            color = self._get_pdf_color(verdict)
            fill_color = self._get_pdf_fill_color(verdict)

            # Add highlight annotation
            highlight = page.add_rect_annot(rect)
            highlight.set_colors(stroke=color, fill=fill_color)
            highlight.set_opacity(0.3)
            highlight.update()

            # Add border
            shape = page.new_shape()
            shape.draw_rect(rect)
            shape.finish(color=color, width=2)
            shape.commit()

    def _get_pdf_color(self, verdict: Verdict) -> tuple[float, float, float]:
        """Get PDF color tuple (0-1 range) for verdict.

        Args:
            verdict: Evaluation verdict

        Returns:
            RGB color tuple with values 0-1
        """
        color = BORDER_COLORS[verdict]
        return (color[0] / 255.0, color[1] / 255.0, color[2] / 255.0)

    def _get_pdf_fill_color(self, verdict: Verdict) -> tuple[float, float, float]:
        """Get PDF fill color tuple for verdict.

        Args:
            verdict: Evaluation verdict

        Returns:
            RGB color tuple with values 0-1
        """
        color = ANNOTATION_COLORS[verdict]
        return (color[0] / 255.0, color[1] / 255.0, color[2] / 255.0)

    def render_to_images(
        self,
        pdf_path: str,
        segments: list[AnnotationSegment],
    ) -> list[Image.Image]:
        """Render annotated PDF pages as images.

        Args:
            pdf_path: Path to the original PDF
            segments: List of segments with verdicts to annotate

        Returns:
            List of PIL Images, one per page
        """
        # First render annotations to PDF
        annotated_pdf = self.render_annotations(pdf_path, segments)

        # Convert to images
        doc = fitz.open(stream=annotated_pdf, filetype="pdf")
        images = []

        try:
            for page in doc:
                # Render page to pixmap
                mat = fitz.Matrix(self.scale, self.scale)
                pix = page.get_pixmap(matrix=mat)

                # Convert to PIL Image
                img = Image.frombytes(
                    "RGB",
                    [pix.width, pix.height],
                    pix.samples,
                )
                images.append(img)

            return images

        finally:
            doc.close()
