# Architecture

This document describes the project structure, design decisions, and future roadmap for the Annotex platform.

## Design Philosophy

**Modular Monolith** - This repository follows a modular monolith architecture:

- **Single entry point** (`app/main.py`) for the entire application
- **Shared database** with unified models
- **Direct imports** between modules (no network overhead)
- **Single deployment unit** (one Docker image, one process)

This approach provides:
- Simple development and debugging
- Easy refactoring with IDE support
- No distributed system complexity
- Natural code sharing between modules

### When to Use Separate Repositories

Truly independent microservices (different teams, different deployment cycles, different tech stacks) should live in **separate repositories**. Services in this repo are closely related and benefit from shared code and coordinated releases.

---

## Current Project Structure

```
annotex/
├── app/
│   ├── main.py                     # FastAPI application entry point
│   │
│   ├── api/
│   │   ├── deps.py                 # Dependency injection (DB, services)
│   │   └── routes/
│   │       ├── evaluation.py       # POST /evaluate, GET /jobs/{id}
│   │       ├── model_answers.py    # Model answer CRUD
│   │       └── submissions.py      # Annotated sheet download
│   │
│   ├── services/
│   │   ├── ocr_service.py          # OCR abstraction + Google Vision
│   │   ├── evaluation_engine.py    # Semantic similarity (sentence-transformers)
│   │   ├── annotation_renderer.py  # PDF annotation rendering (PyMuPDF)
│   │   ├── segmentation_service.py # Question boundary detection
│   │   └── storage_service.py      # File storage abstraction
│   │
│   ├── workers/
│   │   ├── celery_app.py           # Celery configuration
│   │   └── tasks.py                # Background evaluation tasks
│   │
│   ├── models/
│   │   └── database.py             # SQLAlchemy ORM models
│   │
│   ├── schemas/
│   │   └── schemas.py              # Pydantic request/response schemas
│   │
│   ├── core/
│   │   ├── config.py               # Pydantic settings from environment
│   │   └── logging.py              # Structured logging (structlog)
│   │
│   └── db/
│       ├── base.py                 # SQLAlchemy declarative base
│       └── session.py              # Async session factory
│
├── alembic/
│   ├── env.py                      # Migration environment (async)
│   └── versions/                   # Migration scripts
│
├── tests/
│   ├── conftest.py                 # Pytest fixtures
│   ├── test_api/                   # API endpoint tests
│   └── test_services/              # Service unit tests
│
├── docker-compose.yml              # Full stack orchestration
├── Dockerfile                      # Multi-stage container build
├── requirements.txt                # Python dependencies
├── alembic.ini                     # Alembic configuration
├── .env.example                    # Environment template
├── README.md                       # Quick start guide
└── ARCHITECTURE.md                 # This file
```

---

## Module Responsibilities

### `app/api/`
HTTP layer. Handles request validation, authentication, and response formatting. Routes should be thin - delegate business logic to services.

### `app/services/`
Business logic layer. Each service is a focused unit:

| Service | Responsibility |
|---------|----------------|
| `ocr_service.py` | Text extraction from PDFs/images (pluggable providers) |
| `evaluation_engine.py` | Semantic similarity scoring using embeddings |
| `annotation_renderer.py` | Drawing colored annotations on PDFs |
| `segmentation_service.py` | Splitting answer sheets by question |
| `storage_service.py` | File persistence (local/S3) |

### `app/workers/`
Background job processing with Celery. Long-running tasks (OCR, ML inference, PDF rendering) run here to keep API responses fast.

### `app/models/`
Database schema as SQLAlchemy ORM models. Single source of truth for data structure.

### `app/schemas/`
Pydantic models for API request/response validation. Separate from ORM models to allow API evolution independent of database schema.

### `app/core/`
Cross-cutting concerns: configuration, logging, common utilities.

### `app/db/`
Database connection management. Provides async session factory.

---

## Data Flow

```
┌──────────────────────────────────────────────────────────────────┐
│                         API Request                               │
└──────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│  app/api/routes/evaluation.py                                     │
│  - Validate request                                               │
│  - Check model answer exists                                      │
│  - Save uploaded PDF                                              │
│  - Create EvaluationJob (status=queued)                          │
│  - Enqueue Celery task                                           │
│  - Return job_id immediately                                      │
└──────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│  app/workers/tasks.py (Celery)                                    │
│  1. Load job & model answer from DB                               │
│  2. OCR student answer sheet (ocr_service)                        │
│  3. Segment by question (segmentation_service)                    │
│  4. Evaluate each segment (evaluation_engine)                     │
│  5. Render annotations (annotation_renderer)                      │
│  6. Save annotated PDF (storage_service)                          │
│  7. Update job status=completed                                   │
└──────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│  Client polls GET /jobs/{id} until completed                      │
│  Then fetches GET /submissions/{id}/annotated-sheet               │
└──────────────────────────────────────────────────────────────────┘
```

---

## Adding New Features

### Adding a New API Endpoint

1. Create route in `app/api/routes/` (or add to existing file)
2. Add Pydantic schemas in `app/schemas/schemas.py`
3. Register router in `app/main.py` if new file
4. Add tests in `tests/test_api/`

### Adding a New Service

1. Create service in `app/services/`
2. Add dependency provider in `app/api/deps.py`
3. Import in route handlers as needed
4. Add tests in `tests/test_services/`

### Adding a New Database Table

1. Add model in `app/models/database.py`
2. Import in `alembic/env.py` for migration detection
3. Generate migration: `alembic revision --autogenerate -m "description"`
4. Apply: `alembic upgrade head`

---

## Future Structure (Planned Modules)

As the platform grows, new modules will be added following the same pattern:

```
annotex/
├── app/
│   ├── main.py                     # Single entry point (unchanged)
│   │
│   ├── api/routes/
│   │   ├── evaluation.py           # Current
│   │   ├── model_answers.py        # Current
│   │   ├── submissions.py          # Current
│   │   ├── analytics.py            # Future: scoring analytics, trends
│   │   ├── reports.py              # Future: generate PDF reports
│   │   └── webhooks.py             # Future: notify external systems
│   │
│   ├── services/
│   │   ├── ocr_service.py          # Current
│   │   ├── evaluation_engine.py    # Current
│   │   ├── annotation_renderer.py  # Current
│   │   ├── segmentation_service.py # Current
│   │   ├── storage_service.py      # Current
│   │   ├── analytics_service.py    # Future: aggregate scoring data
│   │   ├── report_service.py       # Future: PDF report generation
│   │   └── notification_service.py # Future: email/webhook notifications
│   │
│   ├── models/
│   │   └── database.py             # Extended with new tables as needed
│   │
│   ...
```

### Planned Features

| Module | Purpose | When |
|--------|---------|------|
| `analytics` | Scoring trends, class performance, question difficulty | Phase 2 |
| `reports` | PDF report generation with charts | Phase 2 |
| `notifications` | Email results, webhook callbacks | Phase 3 |
| `rubrics` | Customizable scoring rubrics per question | Phase 3 |
| `batch` | Bulk upload and processing | Phase 3 |

---

## External Services

Services that require **independent deployment** (different team, different release cycle, different scaling needs) belong in separate repositories:

| Service | Repository | Communication |
|---------|------------|---------------|
| Student Management | `student-service` repo | HTTP API |
| Exam Management | `exam-service` repo | HTTP API |
| Authentication | `auth-service` repo | JWT tokens |

This repo stores only `exam_id` and `submission_id` as external references (no foreign key constraints to external databases).

---

## Key Design Decisions

### 1. Single Entry Point
One `main.py` simplifies deployment, debugging, and local development. No service discovery needed.

### 2. Shared Database
All modules use the same PostgreSQL instance. Enables joins, transactions, and referential integrity.

### 3. Direct Imports
Services import each other directly:
```python
from app.services.ocr_service import get_ocr_provider
from app.services.evaluation_engine import EvaluationEngine
```
No network calls, no serialization overhead, IDE refactoring works.

### 4. Background Jobs via Celery
Long-running tasks (OCR, ML, PDF rendering) are offloaded to Celery workers. API stays responsive.

### 5. Pluggable Providers
Services use abstract interfaces (e.g., `OCRProvider`, `StorageBackend`) allowing:
- Mock implementations for testing
- Swap providers without changing business logic (Google Vision → AWS Textract)

### 6. Async Database Access
SQLAlchemy 2.0 async sessions for non-blocking database operations in FastAPI.

---

## Running the Application

### Development
```bash
# Start dependencies
docker-compose up -d db redis

# Run API
uvicorn app.main:app --reload

# Run worker (separate terminal)
celery -A app.workers.celery_app worker --loglevel=info
```

### Production
```bash
docker-compose up -d
docker-compose --profile migrate run migrate
```

### Tests
```bash
pytest tests/ -v
pytest tests/ -v --cov=app --cov-report=html
```
