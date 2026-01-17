"""Storage service tests."""
import pytest

from app.services.storage_service import LocalStorage


class TestLocalStorage:
    """Test local storage backend."""

    @pytest.fixture
    def storage(self, tmp_path):
        """Get local storage with temp directory."""
        return LocalStorage(str(tmp_path))

    @pytest.mark.asyncio
    async def test_save_and_get_bytes(self, storage):
        """Test saving and retrieving bytes."""
        data = b"test content"
        exam_id = "EXAM001"
        submission_id = "SUB001"
        filename = "test.pdf"

        path = await storage.save_bytes(data, exam_id, submission_id, filename)
        retrieved = await storage.get(path)

        assert retrieved == data

    @pytest.mark.asyncio
    async def test_exists(self, storage):
        """Test file existence check."""
        data = b"test content"
        path = await storage.save_bytes(data, "EXAM001", "SUB001", "test.pdf")

        assert await storage.exists(path) is True
        assert await storage.exists("nonexistent/file.pdf") is False

    @pytest.mark.asyncio
    async def test_delete(self, storage):
        """Test file deletion."""
        data = b"test content"
        path = await storage.save_bytes(data, "EXAM001", "SUB001", "test.pdf")

        assert await storage.exists(path) is True
        result = await storage.delete(path)
        assert result is True
        assert await storage.exists(path) is False

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, storage):
        """Test deleting non-existent file."""
        result = await storage.delete("nonexistent/file.pdf")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_url(self, storage):
        """Test getting file URL."""
        data = b"test content"
        path = await storage.save_bytes(data, "EXAM001", "SUB001", "test.pdf")
        url = await storage.get_url(path)

        assert url == path

    def test_compute_checksum(self, storage):
        """Test checksum computation."""
        data = b"test content"
        checksum = storage.compute_checksum(data)

        assert len(checksum) == 64  # SHA256 hex digest
        assert checksum == storage.compute_checksum(data)  # Deterministic

    @pytest.mark.asyncio
    async def test_path_structure(self, storage, tmp_path):
        """Test that files are saved with correct path structure."""
        data = b"test content"
        exam_id = "EXAM001"
        submission_id = "SUB001"
        filename = "test.pdf"

        path = await storage.save_bytes(data, exam_id, submission_id, filename)

        assert exam_id in path
        assert submission_id in path
        assert filename in path
