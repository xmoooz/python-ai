from collections.abc import Callable
from typing import Any, Protocol

from crawl4ai import AsyncWebCrawler

from app.jobs.models import CrawlJobRequest, JobUpsert


class CrawlError(RuntimeError):
    pass


class _CrawlerContext(Protocol):
    async def __aenter__(self) -> Any: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: Any,
    ) -> None: ...


class JobCrawler:
    def __init__(
        self,
        crawler_factory: Callable[[], _CrawlerContext] = AsyncWebCrawler,
    ) -> None:
        self._crawler_factory = crawler_factory

    async def crawl(self, request: CrawlJobRequest) -> JobUpsert:
        source_url = str(request.source_url)
        async with self._crawler_factory() as crawler:
            result = await crawler.arun(url=source_url)

        if not result.success:
            message = result.error_message or "The source page could not be crawled"
            raise CrawlError(message)

        metadata = result.metadata or {}
        title = str(metadata.get("title") or "").strip()
        if not title:
            raise CrawlError("The source page does not provide a title")

        markdown = result.markdown
        if isinstance(markdown, str):
            description = markdown
        else:
            description = getattr(markdown, "raw_markdown", "") if markdown else ""
        description = description.strip()
        if not description:
            raise CrawlError("The source page does not contain readable job content")

        location = request.location.strip() if request.location else None
        is_remote = request.is_remote
        if is_remote is None:
            remote_text = f"{title} {location or ''} {description[:5000]}".casefold()
            is_remote = "remote" in remote_text

        return JobUpsert(
            source_url=source_url,
            title=title,
            company=request.company.strip(),
            location=location,
            is_remote=is_remote,
            description_markdown=description,
        )
