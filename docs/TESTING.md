# Testing Guide

Step-by-step guide to test the Annotex API.

---

## Prerequisites

### 1. Start Services

```bash
docker-compose up -d
docker-compose --profile migrate run migrate
```

### 2. Verify Health

```bash
curl http://localhost:8000/health
```

### 3. Watch Logs (Optional)

In a separate terminal:
```bash
docker-compose logs -f api celery-worker
```

---

## API Testing Workflow

### Step 1: Upload Model Answer

Upload the "correct" answer sheet that student answers will be compared against.

**Request:**
```
POST /api/v1/model-answers?exam_id=EXAM001
Content-Type: multipart/form-data

Body: file = <your_model_answer.pdf>
```

**cURL:**
```bash
curl -X POST "http://localhost:8000/api/v1/model-answers?exam_id=EXAM001" \
  -F "file=@model_answer.pdf"
```

**Response:**
```json
{
  "id": "a1b2c3d4-5678-90ab-cdef-1234567890ab",
  "exam_id": "EXAM001",
  "version": 1,
  "is_active": false,
  "created_at": "2024-01-15T10:30:00Z"
}
```

> **Note:** Save the `id` — you'll need it for the next step.

---

### Step 2: Activate Model Answer

Mark the model answer as the active version for this exam.

**Request:**
```
POST /api/v1/model-answers/{MODEL_ANSWER_ID}/activate
```

**cURL:**
```bash
curl -X POST "http://localhost:8000/api/v1/model-answers/a1b2c3d4-5678-90ab-cdef-1234567890ab/activate"
```

**Response:**
```json
{
  "id": "a1b2c3d4-5678-90ab-cdef-1234567890ab",
  "exam_id": "EXAM001",
  "version": 1,
  "is_active": true
}
```

---

### Step 3: Submit Student Answer for Evaluation

Upload a student's answer sheet to be evaluated against the model answer.

**Request:**
```
POST /api/v1/evaluate?submission_id=STUDENT001&exam_id=EXAM001
Content-Type: multipart/form-data

Body: file = <student_answer.pdf>
```

**cURL:**
```bash
curl -X POST "http://localhost:8000/api/v1/evaluate?submission_id=STUDENT001&exam_id=EXAM001" \
  -F "file=@student_answer.pdf"
```

**Response:**
```json
{
  "id": "e5f6g7h8-1234-56ab-cdef-0987654321ab",
  "submission_id": "STUDENT001",
  "exam_id": "EXAM001",
  "status": "queued",
  "created_at": "2024-01-15T10:35:00Z"
}
```

> **Note:** Save the `id` (job ID) — you'll need it to check status.

---

### Step 4: Poll Job Status

Check if the background processing is complete.

**Request:**
```
GET /api/v1/jobs/{JOB_ID}
```

**cURL:**
```bash
curl "http://localhost:8000/api/v1/jobs/e5f6g7h8-1234-56ab-cdef-0987654321ab"
```

**Response (Processing):**
```json
{
  "id": "e5f6g7h8-1234-56ab-cdef-0987654321ab",
  "submission_id": "STUDENT001",
  "status": "processing",
  "created_at": "2024-01-15T10:35:00Z"
}
```

**Response (Completed):**
```json
{
  "id": "e5f6g7h8-1234-56ab-cdef-0987654321ab",
  "submission_id": "STUDENT001",
  "status": "completed",
  "completed_at": "2024-01-15T10:36:00Z"
}
```

**Response (Failed):**
```json
{
  "id": "e5f6g7h8-1234-56ab-cdef-0987654321ab",
  "status": "failed",
  "error_message": "Error details here..."
}
```

> **Tip:** Keep polling every few seconds until `status` is `completed` or `failed`.

---

### Step 5: Get Detailed Results

View scores and verdicts for each question segment.

**Request:**
```
GET /api/v1/jobs/{JOB_ID}/results
```

**cURL:**
```bash
curl "http://localhost:8000/api/v1/jobs/e5f6g7h8-1234-56ab-cdef-0987654321ab/results"
```

**Response:**
```json
{
  "job": {
    "id": "e5f6g7h8-1234-56ab-cdef-0987654321ab",
    "status": "completed",
    "submission_id": "STUDENT001",
    "exam_id": "EXAM001"
  },
  "segments": [
    {
      "segment": {
        "id": "seg-001",
        "question_number": 1,
        "extracted_text": "The mitochondria is the powerhouse of the cell...",
        "bounding_box": { "page": 0, "x": 50, "y": 100, "width": 500, "height": 80 }
      },
      "result": {
        "similarity_score": 0.85,
        "verdict": "correct",
        "confidence": 0.92,
        "model_answer_reference": "Mitochondria are the powerhouse of the cell..."
      }
    },
    {
      "segment": {
        "id": "seg-002",
        "question_number": 2,
        "extracted_text": "DNA is made of proteins...",
        "bounding_box": { "page": 0, "x": 50, "y": 200, "width": 500, "height": 60 }
      },
      "result": {
        "similarity_score": 0.35,
        "verdict": "incorrect",
        "confidence": 0.88,
        "model_answer_reference": "DNA is made of nucleotides..."
      }
    }
  ]
}
```

---

### Step 6: Download Annotated PDF

Download the PDF with color-coded annotations.

**Request:**
```
GET /api/v1/submissions/{SUBMISSION_ID}/annotated-sheet
```

**cURL:**
```bash
curl -o annotated_STUDENT001.pdf \
  "http://localhost:8000/api/v1/submissions/STUDENT001/annotated-sheet"
```

**Response:** PDF file with annotations

| Color | Verdict | Score Range |
|-------|---------|-------------|
| 🟢 Green | Correct | ≥ 0.75 |
| 🟡 Yellow | Partial | 0.50 - 0.75 |
| 🔴 Red | Incorrect | < 0.50 |

---

## Quick Reference

| Step | Method | Endpoint | Purpose |
|------|--------|----------|---------|
| 1 | POST | `/api/v1/model-answers?exam_id=X` | Upload model answer |
| 2 | POST | `/api/v1/model-answers/{id}/activate` | Activate it |
| 3 | POST | `/api/v1/evaluate?submission_id=X&exam_id=X` | Submit student PDF |
| 4 | GET | `/api/v1/jobs/{job_id}` | Poll status |
| 5 | GET | `/api/v1/jobs/{job_id}/results` | Get detailed scores |
| 6 | GET | `/api/v1/submissions/{submission_id}/annotated-sheet` | Download annotated PDF |

---

## Using Postman

### File Upload in Postman

1. Set method to `POST`
2. Enter URL (e.g., `http://localhost:8000/api/v1/model-answers?exam_id=EXAM001`)
3. Go to **Body** tab
4. Select **form-data**
5. Add key: `file`
6. Hover over key → change type from "Text" to **File**
7. Click "Select Files" → choose your PDF
8. Send

---

## Swagger UI

For interactive testing, open in browser:

```
http://localhost:8000/api/v1/docs
```

---

## Troubleshooting

### Job stuck in "queued" or "processing"

Check Celery worker logs:
```bash
docker-compose logs -f celery-worker
```

### OCR not working

Verify Google credentials:
```bash
docker-compose exec api env | grep GOOGLE
```

### View all logs

```bash
docker-compose logs -f
```
