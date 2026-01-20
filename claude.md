# Annotex - Claude Code Context

## Project Overview

Annotex is a production-grade Python FastAPI backend service for evaluating subjective exam answers with visual annotations. It automates extracting student answers from PDF sheets using OCR, comparing them against model answers using semantic similarity, and rendering color-coded annotations on PDFs.

## Tech Stack

- **Framework**: FastAPI (async), Pydantic v2
- **Database**: PostgreSQL with SQLAlchemy 2.0 (async), Alembic migrations
- **Background Jobs**: Celery with Redis broker
- **ML/AI**: Sentence Transformers (semantic similarity), Google Cloud Vision (OCR)
- **PDF Processing**: PyMuPDF
- **Testing**: pytest, pytest-asyncio
- **Deployment**: Docker, Docker Compose

## Project Structure

```
app/
├── main.py              # FastAPI entry point (CORS, routers, lifespan)
├── api/
│   ├── deps.py          # Dependency injection (DB, services, storage)
│   └── routes/          # API endpoints
├── services/            # Business logic (pluggable providers)
│   ├── ocr_service.py
│   ├── evaluation_engine.py
│   ├── annotation_renderer.py
│   ├── segmentation_service.py
│   └── storage_service.py
├── workers/
│   ├── celery_app.py    # Celery configuration
│   └── tasks.py         # Background task definitions
├── models/
│   └── database.py      # SQLAlchemy ORM models
├── schemas/
│   └── schemas.py       # Pydantic request/response schemas
├── core/
│   ├── config.py        # Settings from environment
│   └── logging.py       # Structured logging
└── db/
    ├── base.py          # SQLAlchemy declarative base
    └── session.py       # Async session factory
```

## Commands

### Development

```bash
# Start services (Docker)
docker-compose up -d

# Run migrations
alembic upgrade head

# Start API (local dev with hot-reload)
uvicorn app.main:app --reload

# Start Celery worker
celery -A app.workers.celery_app worker --loglevel=info
```

### Database Migrations

```bash
# Generate new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Downgrade one step
alembic downgrade -1
```

### Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=app --cov-report=html

# Run specific test file
pytest tests/test_api/test_evaluation.py -v
```

### Docker

```bash
# Start all services
docker-compose up -d

# Run migrations via Docker
docker-compose --profile migrate run migrate

# View logs
docker-compose logs -f api
docker-compose logs -f celery-worker
```

## Architecture Patterns

### Dependency Injection
FastAPI dependencies for DB sessions, services, and storage backends:
```python
async def route(
    db: AsyncSession = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
    ocr: OCRProvider = Depends(get_ocr),
): ...
```

### Pluggable Providers
Services use abstract base classes for swappable implementations:
- `OCRProvider`: MockOCR, GoogleVisionOCR
- `StorageBackend`: LocalStorage, S3Storage

### Async Throughout
- All routes are async
- SQLAlchemy uses async sessions with `asyncpg`
- Celery tasks bridge sync-to-async with event loops

### Background Task Pipeline
Evaluation jobs follow an 8-step Celery pipeline:
1. Load job & model answer
2. OCR student sheet
3. Segment by question
4. Evaluate each segment
5. Render annotations
6. Save annotated PDF
7. Create AnnotatedFile record
8. Update job status

## Database Models

- **ModelAnswer**: Versioned model answers per exam
- **EvaluationJob**: Long-running evaluation tasks (QUEUED → PROCESSING → COMPLETED/FAILED)
- **AnswerSegment**: Individual question answers extracted from PDF
- **EvaluationResult**: Similarity score and verdict (CORRECT ≥0.75, PARTIAL 0.50-0.75, INCORRECT <0.50)
- **AnnotatedFile**: Final annotated PDF output

## API Conventions

- RESTful endpoints under `/api/v1/`
- 202 Accepted for async task submission
- Job status polling: `GET /api/v1/jobs/{id}`
- Pydantic schemas for all request/response validation

## Coding Standards

### Type Hints
- Full type annotations on all functions
- Python 3.11+ syntax (union with `|`)
- Pydantic Field descriptions for API schemas

### Error Handling
- HTTPException with appropriate status codes
- Celery retry with exponential backoff (max 3 retries, 30s base)
- Jobs marked FAILED with error_message on exceptions

### Logging
- Use structlog for structured JSON logging
- Propagate context (job_id, task_id) through logs

### Testing
- Override dependencies with mocks in conftest.py
- Use async fixtures with `@pytest_asyncio.fixture`
- Test database uses SQLite with auto-rollback

## Configuration

Environment variables loaded via Pydantic Settings. See `.env.example` for full reference.

Key settings:
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection for Celery
- `STORAGE_BACKEND`: "local" or "s3"
- `OCR_PROVIDER`: "mock" or "google"
- `CORRECT_THRESHOLD`, `PARTIAL_THRESHOLD`: Verdict thresholds

## Important Files

- `app/main.py`: Application entry point
- `app/core/config.py`: All configuration settings
- `app/workers/tasks.py`: Main evaluation pipeline logic
- `app/services/evaluation_engine.py`: Semantic similarity scoring
- `alembic/versions/`: Database migration history
- `tests/conftest.py`: Test fixtures and dependency overrides
