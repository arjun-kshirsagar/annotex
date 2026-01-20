"""OCR service abstraction with Google Vision implementation."""

import base64
import json
import os
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class BoundingBox:
    """Bounding box for text location."""

    page: int
    x: float
    y: float
    width: float
    height: float

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "page": self.page,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BoundingBox":
        """Create from dictionary."""
        return cls(
            page=data["page"],
            x=data["x"],
            y=data["y"],
            width=data["width"],
            height=data["height"],
        )


@dataclass
class OCRBlock:
    """OCR extracted text block with location."""

    text: str
    bounding_box: BoundingBox
    confidence: float = 1.0
    block_type: str = "paragraph"

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "text": self.text,
            "bounding_box": self.bounding_box.to_dict(),
            "confidence": self.confidence,
            "block_type": self.block_type,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "OCRBlock":
        """Create from dictionary."""
        return cls(
            text=data["text"],
            bounding_box=BoundingBox.from_dict(data["bounding_box"]),
            confidence=data.get("confidence", 1.0),
            block_type=data.get("block_type", "paragraph"),
        )


@dataclass
class OCRPage:
    """OCR results for a single page."""

    page_number: int
    width: float
    height: float
    blocks: list[OCRBlock] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "page_number": self.page_number,
            "width": self.width,
            "height": self.height,
            "blocks": [b.to_dict() for b in self.blocks],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "OCRPage":
        """Create from dictionary."""
        return cls(
            page_number=data["page_number"],
            width=data["width"],
            height=data["height"],
            blocks=[OCRBlock.from_dict(b) for b in data.get("blocks", [])],
        )


@dataclass
class OCRResult:
    """Complete OCR result for a document."""

    pages: list[OCRPage] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {"pages": [p.to_dict() for p in self.pages]}

    @classmethod
    def from_dict(cls, data: dict) -> "OCRResult":
        """Create from dictionary."""
        return cls(pages=[OCRPage.from_dict(p) for p in data.get("pages", [])])

    def get_all_blocks(self) -> list[OCRBlock]:
        """Get all blocks across all pages."""
        blocks = []
        for page in self.pages:
            blocks.extend(page.blocks)
        return blocks


class OCRProvider(ABC):
    """Abstract base class for OCR providers."""

    @abstractmethod
    async def extract_text(self, file_path: str) -> OCRResult:
        """Extract text from a document.

        Args:
            file_path: Path to the PDF or image file

        Returns:
            OCR result with text blocks and positions
        """
        pass

    @abstractmethod
    async def extract_text_from_bytes(self, data: bytes, filename: str) -> OCRResult:
        """Extract text from file bytes.

        Args:
            data: File contents as bytes
            filename: Original filename for type detection

        Returns:
            OCR result with text blocks and positions
        """
        pass


class GoogleVisionOCR(OCRProvider):
    """Google Cloud Vision OCR implementation.

    Supports three credential methods (in priority order):
    1. Base64 encoded service account key (GOOGLE_SERVICE_ACCOUNT_KEY_BASE64)
    2. Path to service account JSON file (GOOGLE_CLOUD_CREDENTIALS_PATH)
    3. Standard Google env var (GOOGLE_APPLICATION_CREDENTIALS)
    """

    def __init__(self):
        """Initialize Google Vision OCR client."""
        self._client = None
        self._temp_credentials_file = None

    def _get_client(self):
        """Lazy load the Vision client with appropriate credentials."""
        if self._client is None:
            from google.cloud import vision
            from google.oauth2 import service_account

            settings = get_settings()
            credentials = None

            # Priority 1: Base64 encoded service account key
            if settings.google_service_account_key_base64:
                try:
                    key_json = base64.b64decode(
                        settings.google_service_account_key_base64
                    ).decode("utf-8")
                    key_dict = json.loads(key_json)
                    credentials = service_account.Credentials.from_service_account_info(
                        key_dict
                    )
                    logger.info("Using base64 encoded Google credentials")
                except Exception as e:
                    logger.error(
                        "Failed to decode base64 credentials",
                        error=str(e),
                    )
                    raise ValueError("Invalid GOOGLE_SERVICE_ACCOUNT_KEY_BASE64") from e

            # Priority 2: Credentials file path
            elif settings.get_google_credentials_path():
                credentials_path = settings.get_google_credentials_path()
                if not os.path.exists(credentials_path):
                    raise FileNotFoundError(
                        f"Google credentials file not found: {credentials_path}"
                    )
                credentials = service_account.Credentials.from_service_account_file(
                    credentials_path
                )
                logger.info(
                    "Using Google credentials from file",
                    path=credentials_path,
                )

            # Priority 3: Default credentials (ADC)
            else:
                # Let Google SDK use Application Default Credentials
                logger.info("Using Google Application Default Credentials")

            if credentials:
                self._client = vision.ImageAnnotatorClient(credentials=credentials)
            else:
                self._client = vision.ImageAnnotatorClient()

        return self._client

    def __del__(self):
        """Clean up temporary credentials file if created."""
        if self._temp_credentials_file and os.path.exists(self._temp_credentials_file):
            os.remove(self._temp_credentials_file)

    async def extract_text(self, file_path: str) -> OCRResult:
        """Extract text from a PDF or image file using Google Vision."""
        path = Path(file_path)
        with open(path, "rb") as f:
            data = f.read()
        return await self.extract_text_from_bytes(data, path.name)

    async def extract_text_from_bytes(self, data: bytes, filename: str) -> OCRResult:
        """Extract text from file bytes using Google Vision."""
        from google.cloud import vision

        client = self._get_client()
        is_pdf = filename.lower().endswith(".pdf")

        if is_pdf:
            return await self._process_pdf(client, data)
        else:
            return await self._process_image(client, data, page_number=0)

    async def _process_pdf(self, client, data: bytes) -> OCRResult:
        """Process PDF document with Google Vision."""
        from google.cloud import vision

        input_config = vision.InputConfig(
            content=data,
            mime_type="application/pdf",
        )

        feature = vision.Feature(type_=vision.Feature.Type.DOCUMENT_TEXT_DETECTION)

        request = vision.AnnotateFileRequest(
            input_config=input_config,
            features=[feature],
        )

        response = client.batch_annotate_files(requests=[request])
        pages = []

        for resp in response.responses:
            for i, page_response in enumerate(resp.responses):
                if page_response.full_text_annotation:
                    ocr_page = self._parse_page_annotation(
                        page_response.full_text_annotation, i
                    )
                    pages.append(ocr_page)

        logger.info(
            "Extracted text from PDF with Google Vision",
            page_count=len(pages),
        )
        return OCRResult(pages=pages)

    async def _process_image(self, client, data: bytes, page_number: int) -> OCRResult:
        """Process single image with Google Vision."""
        from google.cloud import vision

        image = vision.Image(content=data)
        response = client.document_text_detection(image=image)

        if response.full_text_annotation:
            ocr_page = self._parse_page_annotation(
                response.full_text_annotation, page_number
            )
            return OCRResult(pages=[ocr_page])

        return OCRResult(pages=[])

    def _parse_page_annotation(self, annotation, page_number: int) -> OCRPage:
        """Parse Google Vision annotation into OCRPage."""
        blocks = []
        page_width = 0.0
        page_height = 0.0

        for page in annotation.pages:
            page_width = page.width
            page_height = page.height

            for block in page.blocks:
                text_parts = []
                for paragraph in block.paragraphs:
                    for word in paragraph.words:
                        word_text = "".join(symbol.text for symbol in word.symbols)
                        text_parts.append(word_text)

                text = " ".join(text_parts)
                if not text.strip():
                    continue

                vertices = block.bounding_box.vertices
                x_coords = [v.x for v in vertices if v.x is not None]
                y_coords = [v.y for v in vertices if v.y is not None]

                if not x_coords or not y_coords:
                    logger.warning(
                        "Skipping block with no vertices/coordinates", text=text[:50]
                    )
                    continue

                bbox = BoundingBox(
                    page=page_number,
                    x=min(x_coords),
                    y=min(y_coords),
                    width=max(x_coords) - min(x_coords),
                    height=max(y_coords) - min(y_coords),
                )

                confidence = sum(
                    word.confidence for para in block.paragraphs for word in para.words
                ) / max(
                    sum(len(para.words) for para in block.paragraphs),
                    1,
                )

                blocks.append(
                    OCRBlock(
                        text=text,
                        bounding_box=bbox,
                        confidence=confidence,
                        block_type="paragraph",
                    )
                )

        return OCRPage(
            page_number=page_number,
            width=page_width,
            height=page_height,
            blocks=blocks,
        )


class MockOCR(OCRProvider):
    """Mock OCR provider for testing."""

    def __init__(self, mock_responses: dict[str, OCRResult] | None = None):
        """Initialize mock OCR.

        Args:
            mock_responses: Optional dict mapping file paths to OCR results
        """
        self.mock_responses = mock_responses or {}
        self.default_response = OCRResult(
            pages=[
                OCRPage(
                    page_number=0,
                    width=612.0,
                    height=792.0,
                    blocks=[
                        OCRBlock(
                            text="Q1. Sample question answer text for testing.",
                            bounding_box=BoundingBox(
                                page=0, x=50, y=100, width=500, height=50
                            ),
                            confidence=0.95,
                        ),
                        OCRBlock(
                            text="Q2. Another sample answer text.",
                            bounding_box=BoundingBox(
                                page=0, x=50, y=200, width=500, height=50
                            ),
                            confidence=0.92,
                        ),
                    ],
                )
            ]
        )

    async def extract_text(self, file_path: str) -> OCRResult:
        """Return mock OCR result."""
        logger.info("Mock OCR extracting text", file_path=file_path)
        return self.mock_responses.get(file_path, self.default_response)

    async def extract_text_from_bytes(self, data: bytes, filename: str) -> OCRResult:
        """Return mock OCR result."""
        logger.info("Mock OCR extracting text from bytes", filename=filename)
        return self.mock_responses.get(filename, self.default_response)


def get_ocr_provider() -> OCRProvider:
    """Get OCR provider based on configuration.

    Returns:
        Configured OCR provider instance
    """
    settings = get_settings()
    if settings.ocr_provider == "google_vision":
        return GoogleVisionOCR()
    elif settings.ocr_provider == "mock":
        return MockOCR()
    else:
        raise ValueError(f"Unsupported OCR provider: {settings.ocr_provider}")
