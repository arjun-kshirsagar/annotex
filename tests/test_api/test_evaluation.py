"""Evaluation endpoint tests."""
import io
import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_submit_evaluation(
    client: AsyncClient,
    sample_pdf_bytes: bytes,
    sample_exam_id: str,
    sample_submission_id: str,
):
    """Test submitting an evaluation job."""
    # Create and activate model answer first
    files = {"file": ("model_answer.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
    create_response = await client.post(
        f"/api/v1/model-answers?exam_id={sample_exam_id}",
        files=files,
    )
    model_answer_id = create_response.json()["id"]
    await client.post(f"/api/v1/model-answers/{model_answer_id}/activate")

    # Submit evaluation
    files = {"file": ("student_answer.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
    response = await client.post(
        f"/api/v1/evaluate?submission_id={sample_submission_id}&exam_id={sample_exam_id}",
        files=files,
    )

    assert response.status_code == 202
    data = response.json()
    assert data["submission_id"] == sample_submission_id
    assert data["exam_id"] == sample_exam_id
    assert data["status"] == "queued"


@pytest.mark.asyncio
async def test_submit_evaluation_no_active_model_answer(
    client: AsyncClient,
    sample_pdf_bytes: bytes,
    sample_exam_id: str,
    sample_submission_id: str,
):
    """Test submitting evaluation without active model answer."""
    files = {"file": ("student_answer.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
    response = await client.post(
        f"/api/v1/evaluate?submission_id={sample_submission_id}&exam_id={sample_exam_id}",
        files=files,
    )

    assert response.status_code == 404
    assert "active model answer" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_submit_evaluation_duplicate(
    client: AsyncClient,
    sample_pdf_bytes: bytes,
    sample_exam_id: str,
    sample_submission_id: str,
):
    """Test submitting duplicate evaluation."""
    # Create and activate model answer
    files = {"file": ("model_answer.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
    create_response = await client.post(
        f"/api/v1/model-answers?exam_id={sample_exam_id}",
        files=files,
    )
    model_answer_id = create_response.json()["id"]
    await client.post(f"/api/v1/model-answers/{model_answer_id}/activate")

    # Submit first evaluation
    files = {"file": ("student_answer.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
    await client.post(
        f"/api/v1/evaluate?submission_id={sample_submission_id}&exam_id={sample_exam_id}",
        files=files,
    )

    # Submit duplicate
    files = {"file": ("student_answer.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
    response = await client.post(
        f"/api/v1/evaluate?submission_id={sample_submission_id}&exam_id={sample_exam_id}",
        files=files,
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_get_job_status(
    client: AsyncClient,
    sample_pdf_bytes: bytes,
    sample_exam_id: str,
    sample_submission_id: str,
):
    """Test getting job status."""
    # Create and activate model answer
    files = {"file": ("model_answer.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
    create_response = await client.post(
        f"/api/v1/model-answers?exam_id={sample_exam_id}",
        files=files,
    )
    model_answer_id = create_response.json()["id"]
    await client.post(f"/api/v1/model-answers/{model_answer_id}/activate")

    # Submit evaluation
    files = {"file": ("student_answer.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")}
    submit_response = await client.post(
        f"/api/v1/evaluate?submission_id={sample_submission_id}&exam_id={sample_exam_id}",
        files=files,
    )
    job_id = submit_response.json()["id"]

    # Get status
    response = await client.get(f"/api/v1/jobs/{job_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == job_id
    assert "status" in data


@pytest.mark.asyncio
async def test_get_job_status_not_found(client: AsyncClient):
    """Test getting status of non-existent job."""
    fake_id = str(uuid.uuid4())
    response = await client.get(f"/api/v1/jobs/{fake_id}")

    assert response.status_code == 404
