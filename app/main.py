from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.db import close_pool, get_pool, run_migrations
from app.jobs.router import router as jobs_router


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    pool = await get_pool()
    await run_migrations(pool)
    yield
    await close_pool()


def create_app() -> FastAPI:
    settings = get_settings()
    logging.getLogger().setLevel(settings.log_level)

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        docs_url=settings.docs_url,
        redoc_url=settings.redoc_url,
        openapi_url=settings.openapi_url,
        lifespan=lifespan,
    )

    if settings.cors_origins:
        allow_all = settings.cors_origins == ["*"]
        application.add_middleware(
            CORSMiddleware,
            allow_origins=["*"] if allow_all else settings.cors_origins,
            allow_credentials=not allow_all,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    application.include_router(jobs_router)

    @application.get("/health")
    async def health() -> JSONResponse:
        current = get_settings()
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return JSONResponse(
                {"status": "ok", "db": "connected", "env": current.app_env}
            )
        except Exception as exc:
            detail = str(exc) if current.debug else "unavailable"
            return JSONResponse(
                {"status": "error", "db": detail, "env": current.app_env},
                status_code=503,
            )

    return application


app = create_app()
