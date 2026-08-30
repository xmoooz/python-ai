from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import ROOT_DIR, get_settings
from app.db import close_pool, get_pool


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    await get_pool()
    yield
    await close_pool()


def create_app() -> FastAPI:
    settings = get_settings()
    gym_frontend = ROOT_DIR / "app" / "static" / "gym"
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

    if gym_frontend.is_dir():
        application.mount(
            "/gym",
            StaticFiles(directory=gym_frontend, html=True),
            name="gym",
        )

    @application.get("/", include_in_schema=False, response_model=None)
    async def home() -> RedirectResponse | JSONResponse:
        if gym_frontend.is_dir():
            return RedirectResponse("/gym/")
        return JSONResponse(
            {
                "message": "Gym frontend is not built",
                "build": "cd frontend && npm install && npm run build",
            },
            status_code=503,
        )

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
