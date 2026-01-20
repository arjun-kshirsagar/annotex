"""Model answer endpoint tests."""

import io
import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_model_answer(
    client: AsyncClient, sample_pdf_bytes: bytes, sample_exam_id: str
):
    """Test creating a new model answer."""
    files = {"file": ("model_answer.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
    response = await client.post(
        f"/api/v1/model-answers?exam_id={sample_exam_id}",
        files=files,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["exam_id"] == sample_exam_id
    assert data["version"] == 1
    assert data["is_active"] is False


@pytest.mark.asyncio
async def test_create_model_answer_invalid_file_type(client: AsyncClient, sample_exam_id: str):
    """Test creating model answer with non-PDF file."""
    files = {"file": ("document.txt", io.BytesIO(b"text content"), "text/plain")}
    response = await client.post(
        f"/api/v1/model-answers?exam_id={sample_exam_id}",
        files=files,
    )

    assert response.status_code == 400
    assert "PDF" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_model_answer(client: AsyncClient, sample_pdf_bytes: bytes, sample_exam_id: str):
    """Test getting a model answer by ID."""
    # Create model answer first
    files = {"file": ("model_answer.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
    create_response = await client.post(
        f"/api/v1/model-answers?exam_id={sample_exam_id}",
        files=files,
    )
    model_answer_id = create_response.json()["id"]

    # Get the model answer
    response = await client.get(f"/api/v1/model-answers/{model_answer_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == model_answer_id
    assert data["exam_id"] == sample_exam_id


@pytest.mark.asyncio
async def test_get_model_answer_not_found(client: AsyncClient):
    """Test getting non-existent model answer."""
    fake_id = str(uuid.uuid4())
    response = await client.get(f"/api/v1/model-answers/{fake_id}")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_model_answers_for_exam(
    client: AsyncClient, sample_pdf_bytes: bytes, sample_exam_id: str
):
    """Test listing model answers for an exam."""
    # Create two versions
    for _ in range(2):
        files = {"file": ("model_answer.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
        await client.post(
            f"/api/v1/model-answers?exam_id={sample_exam_id}",
            files=files,
        )

    # List model answers
    response = await client.get(f"/api/v1/exams/{sample_exam_id}/model-answers")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_activate_model_answer(
    client: AsyncClient, sample_pdf_bytes: bytes, sample_exam_id: str
):
    """Test activating a model answer."""
    # Create model answer
    files = {"file": ("model_answer.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
    create_response = await client.post(
        f"/api/v1/model-answers?exam_id={sample_exam_id}",
        files=files,
    )
    model_answer_id = create_response.json()["id"]

    # Activate it
    response = await client.post(f"/api/v1/model-answers/{model_answer_id}/activate")

    assert response.status_code == 200
    data = response.json()
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_get_active_model_answer(
    client: AsyncClient, sample_pdf_bytes: bytes, sample_exam_id: str
):
    """Test getting active model answer for exam."""
    # Create and activate model answer
    files = {"file": ("model_answer.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
    create_response = await client.post(
        f"/api/v1/model-answers?exam_id={sample_exam_id}",
        files=files,
    )
    model_answer_id = create_response.json()["id"]
    await client.post(f"/api/v1/model-answers/{model_answer_id}/activate")

    # Get active model answer
    response = await client.get(f"/api/v1/exams/{sample_exam_id}/active-model-answer")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == model_answer_id
    assert data["is_active"] is True
