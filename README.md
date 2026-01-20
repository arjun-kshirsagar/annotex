# Annotex

A production-grade Python FastAPI backend for evaluating subjective exam answers with visual annotations (green/yellow/red markings).

## Documentation

| Document | Description |
|----------|-------------|
| [Architecture](docs/ARCHITECTURE.md) | Project structure, design decisions, future roadmap |
| [Testing Guide](docs/TESTING.md) | Step-by-step API testing workflow |

## Features

- **PDF Answer Sheet Processing**: OCR extraction and question segmentation
- **Semantic Similarity Evaluation**: Using sentence transformers for answer comparison
- **Visual Annotations**: Color-coded markings (green=correct, yellow=partial, red=incorrect)
- **Versioned Model Answers**: Multiple versions per exam with activation control
- **Async Processing**: Celery-based background job processing
- **RESTful API**: FastAPI with OpenAPI documentation

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   FastAPI API   │────▶│  PostgreSQL DB  │     │     Redis       │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                                               │
        │                                               │
        ▼                                               ▼
┌─────────────────┐                           ┌─────────────────┐
│  File Storage   │◀──────────────────────────│  Celery Worker  │
└─────────────────┘                           └─────────────────┘
```

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for local development)

### Using Docker Compose

```bash
# Start all services
docker-compose up -d

# Run database migrations
docker-compose --profile migrate run migrate

# Check API health
curl http://localhost:8000/health

# View logs
docker-compose logs -f api # if you dont add api, it will print logs of all services
```

### Local Development

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env

# Start PostgreSQL and Redis (using Docker)
docker-compose up -d db redis

# Run migrations
alembic upgrade head

# Start the API server
uvicorn app.main:app --reload

# Start Celery worker (in separate terminal)
celery -A app.workers.celery_app worker --loglevel=info
```

## API Documentation

Once running, access the API documentation at:

- Swagger UI: http://localhost:8000/api/v1/docs
- ReDoc: http://localhost:8000/api/v1/redoc

## API Endpoints

### Model Answers

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/model-answers` | Upload model answer PDF |
| GET | `/api/v1/model-answers/{id}` | Get model answer metadata |
| GET | `/api/v1/exams/{exam_id}/model-answers` | List versions for exam |
| POST | `/api/v1/model-answers/{id}/activate` | Set as active version |
| GET | `/api/v1/exams/{exam_id}/active-model-answer` | Get active model answer |

### Evaluation

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/evaluate` | Submit evaluation job |
| GET | `/api/v1/jobs/{job_id}` | Get job status |
| GET | `/api/v1/jobs/{job_id}/results` | Get detailed results |

### Submissions

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/submissions/{submission_id}/annotated-sheet` | Download annotated PDF |
| GET | `/api/v1/submissions/{submission_id}/annotated-sheet/metadata` | Get metadata |

## Usage Example

### 1. Upload Model Answer

```bash
curl -X POST "http://localhost:8000/api/v1/model-answers?exam_id=EXAM001" \
  -F "file=@model_answer.pdf"
```

Response:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "exam_id": "EXAM001",
  "version": 1,
  "is_active": false
}
```

### 2. Activate Model Answer

```bash
curl -X POST "http://localhost:8000/api/v1/model-answers/550e8400-e29b-41d4-a716-446655440000/activate"
```

### 3. Submit Evaluation

```bash
curl -X POST "http://localhost:8000/api/v1/evaluate?submission_id=SUB001&exam_id=EXAM001" \
  -F "file=@student_answer.pdf"
```

Response:
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440001",
  "submission_id": "SUB001",
  "status": "queued"
}
```

### 4. Poll Job Status

```bash
curl "http://localhost:8000/api/v1/jobs/660e8400-e29b-41d4-a716-446655440001"
```

### 5. Get Results

```bash
curl "http://localhost:8000/api/v1/jobs/660e8400-e29b-41d4-a716-446655440001/results"
```

### 6. Download Annotated PDF

```bash
curl -o annotated.pdf "http://localhost:8000/api/v1/submissions/SUB001/annotated-sheet"
```

## Verdict Thresholds

| Verdict | Similarity Score | Annotation Color |
|---------|-----------------|------------------|
| correct | ≥ 0.75 | 🟢 Green |
| partial | 0.50 - 0.75 | 🟡 Yellow |
| incorrect | < 0.50 | 🔴 Red |

## Configuration

Configuration is managed through environment variables. See `.env.example` for all options.

### Key Configuration Options

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://...` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `OCR_PROVIDER` | OCR provider (`google_vision` or `mock`) | `mock` |
| `CORRECT_THRESHOLD` | Threshold for correct verdict | `0.75` |
| `PARTIAL_THRESHOLD` | Threshold for partial verdict | `0.50` |
| `EMBEDDING_MODEL` | Sentence transformer model | `all-MiniLM-L6-v2` |

### Google Cloud Vision Setup

For production OCR:

1. Create a Google Cloud project
2. Enable the Vision API
3. Create a service account and download credentials JSON
4. Set environment variables:
   ```bash
   OCR_PROVIDER=google_vision
   GOOGLE_CLOUD_CREDENTIALS_PATH=/path/to/credentials.json
   ```

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=app --cov-report=html

# Run specific test file
pytest tests/test_api/test_evaluation.py -v
```

## Project Structure

```
annotex/
├── app/
│   ├── main.py                  # Single entry point
│   ├── api/
│   │   ├── deps.py              # Dependency injection
│   │   └── routes/              # API endpoints
│   ├── services/                # Business logic
│   ├── workers/                 # Celery background tasks
│   ├── models/                  # SQLAlchemy ORM models
│   ├── schemas/                 # Pydantic schemas
│   ├── core/                    # Config, logging
│   └── db/                      # Database session
├── alembic/                     # Database migrations
├── tests/                       # Test suite
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

See [docs/](docs/) for detailed documentation.

## License

MIT
