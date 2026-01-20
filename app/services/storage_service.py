"""File storage abstraction."""

import hashlib
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class StorageBackend(ABC):
    """Abstract base class for storage backends."""

    @abstractmethod
    async def save(
        self,
        file: BinaryIO,
        exam_id: str,
        submission_id: str,
        filename: str,
    ) -> str:
        """Save file to storage.

        Args:
            file: File-like object to save
            exam_id: Exam identifier
            submission_id: Submission identifier
            filename: Name of the file

        Returns:
            Path where file was saved
        """
        pass

    @abstractmethod
    async def save_bytes(
        self,
        data: bytes,
        exam_id: str,
        submission_id: str,
        filename: str,
    ) -> str:
        """Save bytes to storage.

        Args:
            data: Bytes to save
            exam_id: Exam identifier
            submission_id: Submission identifier
            filename: Name of the file

        Returns:
            Path where file was saved
        """
        pass

    @abstractmethod
    async def get(self, path: str) -> bytes:
        """Get file contents from storage.

        Args:
            path: Path to the file

        Returns:
            File contents as bytes
        """
        pass

    @abstractmethod
    async def exists(self, path: str) -> bool:
        """Check if file exists in storage.

        Args:
            path: Path to the file

        Returns:
            True if file exists, False otherwise
        """
        pass

    @abstractmethod
    async def get_url(self, path: str) -> str:
        """Get URL or path for file access.

        Args:
            path: Path to the file

        Returns:
            URL or path for accessing the file
        """
        pass

    @abstractmethod
    async def delete(self, path: str) -> bool:
        """Delete file from storage.

        Args:
            path: Path to the file

        Returns:
            True if file was deleted, False otherwise
        """
        pass

    @staticmethod
    def compute_checksum(data: bytes) -> str:
        """Compute SHA256 checksum of data.

        Args:
            data: Bytes to compute checksum for

        Returns:
            SHA256 hex digest
        """
        return hashlib.sha256(data).hexdigest()


class LocalStorage(StorageBackend):
    """Local filesystem storage backend."""

    def __init__(self, base_path: str | None = None):
        """Initialize local storage.

        Args:
            base_path: Base directory for storage
        """
        settings = get_settings()
        self.base_path = Path(base_path or settings.storage_base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info("Initialized local storage", base_path=str(self.base_path))

    def _get_path(self, exam_id: str, submission_id: str, filename: str) -> Path:
        """Get full path for a file.

        Args:
            exam_id: Exam identifier
            submission_id: Submission identifier
            filename: Name of the file

        Returns:
            Full path to the file
        """
        return self.base_path / exam_id / submission_id / filename

    async def save(
        self,
        file: BinaryIO,
        exam_id: str,
        submission_id: str,
        filename: str,
    ) -> str:
        """Save file to local storage."""
        path = self._get_path(exam_id, submission_id, filename)
        path.parent.mkdir(parents=True, exist_ok=True)

        path.write_bytes(file.read())

        logger.info(
            "Saved file to local storage",
            path=str(path),
            exam_id=exam_id,
            submission_id=submission_id,
        )
        return str(path)

    async def save_bytes(
        self,
        data: bytes,
        exam_id: str,
        submission_id: str,
        filename: str,
    ) -> str:
        """Save bytes to local storage."""
        path = self._get_path(exam_id, submission_id, filename)
        path.parent.mkdir(parents=True, exist_ok=True)

        path.write_bytes(data)

        logger.info(
            "Saved bytes to local storage",
            path=str(path),
            size=len(data),
            exam_id=exam_id,
            submission_id=submission_id,
        )
        return str(path)

    async def get(self, path: str) -> bytes:
        """Get file contents from local storage."""
        full_path = Path(path)
        if not full_path.is_absolute():
            full_path = self.base_path / path

        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        return full_path.read_bytes()

    async def exists(self, path: str) -> bool:
        """Check if file exists in local storage."""
        full_path = Path(path)
        if not full_path.is_absolute():
            full_path = self.base_path / path
        return full_path.exists()

    async def get_url(self, path: str) -> str:
        """Get path for file access."""
        full_path = Path(path)
        if not full_path.is_absolute():
            full_path = self.base_path / path
        return str(full_path)

    async def delete(self, path: str) -> bool:
        """Delete file from local storage."""
        full_path = Path(path)
        if not full_path.is_absolute():
            full_path = self.base_path / path

        if full_path.exists():
            os.remove(full_path)
            logger.info("Deleted file from local storage", path=str(full_path))
            return True
        return False


def get_storage_backend() -> StorageBackend:
    """Get storage backend based on configuration.

    Returns:
        Configured storage backend instance
    """
    settings = get_settings()
    if settings.storage_backend == "local":
        return LocalStorage()
    else:
        raise ValueError(f"Unsupported storage backend: {settings.storage_backend}")
