from hmac import compare_digest
import logging
from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import HttpUrl

from app.config import Settings, get_settings
from app.db import get_db
from app.jobs.crawler import CrawlError, JobCrawler
from app.jobs.models import CrawlJobRequest, Job, JobList
from app.jobs.repository import JobRepository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])
_crawler = JobCrawler()


def get_job_repository(
    connection: Annotated[asyncpg.Connection, Depends(get_db)],
) -> JobRepository:
    return JobRepository(connection)


def get_job_crawler() -> JobCrawler:
    return _crawler


def require_ingestion_access(
    ingestion_key: Annotated[str | None, Header(alias="X-Ingestion-Key")] = None,
    settings: Settings = Depends(get_settings),
) -> Settings:
    configured_key = settings.job_ingestion_key
    if configured_key is None or not settings.job_source_hosts:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Job ingestion is not configured",
        )
    if ingestion_key is None or not compare_digest(
        ingestion_key,
        configured_key.get_secret_value(),
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid ingestion key",
        )
    return settings


def source_host_is_allowed(url: HttpUrl, allowed_hosts: list[str]) -> bool:
    if url.scheme != "https":
        return False
    host = (url.host or "").rstrip(".").casefold()
    return any(
        host == allowed.rstrip(".").casefold()
        or host.endswith(f".{allowed.rstrip('.').casefold()}")
        for allowed in allowed_hosts
    )


@router.post("/crawl", response_model=Job)
async def crawl_job(
    request: CrawlJobRequest,
    repository: Annotated[JobRepository, Depends(get_job_repository)],
    crawler: Annotated[JobCrawler, Depends(get_job_crawler)],
    settings: Annotated[Settings, Depends(require_ingestion_access)],
) -> Job:
    if not source_host_is_allowed(request.source_url, settings.job_source_hosts):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source host is not allowed",
        )

    try:
        job = await crawler.crawl(request)
    except CrawlError as exc:
        logger.warning("Job crawl failed for %s: %s", request.source_url, exc)
        detail = str(exc) if settings.debug else "The job page could not be processed"
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=detail,
        ) from exc
    return await repository.upsert(job)


@router.get("", response_model=JobList)
async def list_jobs(
    repository: Annotated[JobRepository, Depends(get_job_repository)],
    query: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    location: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    remote: bool | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> JobList:
    return await repository.list(
        query=query,
        location=location,
        remote=remote,
        limit=limit,
        offset=offset,
    )


@router.get("/{job_id}", response_model=Job)
async def get_job(
    job_id: int,
    repository: Annotated[JobRepository, Depends(get_job_repository)],
) -> Job:
    job = await repository.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )
    return job
