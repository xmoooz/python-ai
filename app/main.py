from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.db import close_pool, get_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await get_db()
    yield
    await close_pool()


app = FastAPI(title="AI Microservice", lifespan=lifespan)


@app.get("/health")
async def health() -> JSONResponse:
    settings = get_settings()
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return JSONResponse({"status": "ok", "db": "connected", "env": settings.app_env})
    except Exception as e:
        return JSONResponse({"status": "error", "db": str(e)}, status_code=503)
