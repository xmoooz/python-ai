# python-ai

FastAPI service for collecting and searching entry-level job postings.

## Development

```bash
cp .env.example .env
cp .env.dev.example .env.dev
docker compose up -d
uv sync
uv run crawl4ai-setup
uv run uvicorn app.main:app --reload
```

The application applies SQL migrations at startup. Open
`http://127.0.0.1:8000/docs` for the API documentation.

## Job API

Configure `JOB_INGESTION_KEY` and a comma-separated `JOB_SOURCE_HOSTS`
allowlist in the active environment file. Ingest one public job page:

```bash
curl -X POST http://127.0.0.1:8000/jobs/crawl \
  -H "Content-Type: application/json" \
  -H "X-Ingestion-Key: change-me" \
  -d '{
    "source_url": "https://boards.greenhouse.io/example/jobs/123",
    "company": "Example",
    "location": "New York, NY"
  }'
```

Search stored jobs:

```bash
curl "http://127.0.0.1:8000/jobs?query=python&remote=true"
```