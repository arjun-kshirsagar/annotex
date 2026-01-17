"""Test configuration and fixtures."""
import asyncio
import os
import uuid
from collections.abc import AsyncGenerator, Generator
from typing import Any

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

# Set test environment
os.environ["OCR_PROVIDER"] = "mock"
os.environ["STORAGE_BASE_PATH"] = "/tmp/test_storage"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"

from app.api.deps import get_db, get_ocr, get_storage
from app.core.config import Settings, get_settings
from app.db.base import Base
from app.main import app
from app.services.ocr_service import MockOCR
from app.services.storage_service import LocalStorage


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Get test settings."""
    return Settings(
        database_url="sqlite+aiosqlite:///./test.db",
        ocr_provider="mock",
        storage_backend="local",
        storage_base_path="/tmp/test_storage",
    )


@pytest_asyncio.fixture(scope="function")
async def async_engine():
    """Create async test database engine."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///./test.db",
        echo=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Get async database session for tests."""
    async_session_maker = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_maker() as session:
        yield session
        await session.rollback()


@pytest.fixture
def mock_ocr() -> MockOCR:
    """Get mock OCR provider."""
    return MockOCR()


@pytest.fixture
def mock_storage(tmp_path) -> LocalStorage:
    """Get mock storage with temp directory."""
    return LocalStorage(str(tmp_path))


@pytest_asyncio.fixture
async def client(db_session, mock_ocr, mock_storage) -> AsyncGenerator[AsyncClient, None]:
    """Get async test client."""

    async def override_get_db():
        yield db_session

    def override_get_ocr():
        return mock_ocr

    def override_get_storage():
        return mock_storage

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_ocr] = override_get_ocr
    app.dependency_overrides[get_storage] = override_get_storage

    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def sync_client(db_session, mock_ocr, mock_storage) -> Generator[TestClient, None, None]:
    """Get sync test client."""

    async def override_get_db():
        yield db_session

    def override_get_ocr():
        return mock_ocr

    def override_get_storage():
        return mock_storage

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_ocr] = override_get_ocr
    app.dependency_overrides[get_storage] = override_get_storage

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture
def sample_pdf_bytes() -> bytes:
    """Generate minimal valid PDF bytes for testing."""
    # Minimal valid PDF structure
    pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>
endobj
xref
0 4
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
trailer
<< /Size 4 /Root 1 0 R >>
startxref
196
%%EOF"""
    return pdf_content


@pytest.fixture
def sample_exam_id() -> str:
    """Get sample exam ID."""
    return f"EXAM_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def sample_submission_id() -> str:
    """Get sample submission ID."""
    return f"SUB_{uuid.uuid4().hex[:8]}"
