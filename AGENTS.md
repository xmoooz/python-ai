# Python AI Service Guide

## Purpose
- This repository is a Python 3.13+ FastAPI microservice backed by PostgreSQL 18 and pgvector.
- The API currently exposes `/health`; add new HTTP features under `app/`.
- PostgreSQL runs in Docker. The FastAPI application runs locally during development.

## Development
1. Start the database: `docker compose up -d`.
2. Install/sync Python and dependencies: `uv sync`.
3. Run the API: `uv run uvicorn app.main:app --reload`.
4. Open `http://127.0.0.1:8000/docs` or `/health`.

Use `uv` for dependency and command management. Keep `uv.lock` committed. Do not install project packages globally.

## Configuration
- Supported `APP_ENV` values: `dev`, `test`, `staging`, and `prod`.
- Settings load in this order: code defaults, `.env`, `.env.<profile>`, process environment.
- Copy example files to untracked local files; never commit credentials or API keys.
- Keep shared Docker values in `.env` and profile-specific app values in `.env.<profile>`.
- Production must keep debug/docs disabled and use a non-default database password.

## Database
- Compose uses `pgvector/pgvector:0.8.6-pg18-trixie`.
- PostgreSQL 18 data is mounted at `/var/lib/postgresql`; do not change it to the pre-18 path.
- `docker/postgres/init/01-vector.sql` enables pgvector only when a fresh volume is initialized.
- Use asyncpg through the shared pool in `app/db.py`; do not create connections in route handlers.
- Use parameterized SQL. Never interpolate user input into SQL strings.
- Do not remove or recreate the named data volume unless data loss is explicitly intended.

## Code Conventions
- Use modern Python type annotations and async I/O.
- Keep configuration in `app/config.py`; do not read environment variables throughout the app.
- Build the application through `create_app()` and release resources in its lifespan.
- Do not expose secrets or raw internal errors in production responses.
- Add focused tests for new behavior and use a separate test database.

## Verification
- Run the relevant tests and linters when available.
- At minimum, verify imports and startup with `uv run python -c "import app.main"`.
- For database changes, confirm `docker compose ps` is healthy and call `/health`.
