from types import SimpleNamespace
import unittest

from app.jobs.crawler import CrawlError, JobCrawler
from app.jobs.models import CrawlJobRequest
from app.jobs.repository import JobRepository
from app.jobs.router import source_host_is_allowed


class FakeCrawlerContext:
    def __init__(self, result: SimpleNamespace) -> None:
        self.result = result
        self.requested_url: str | None = None

    async def __aenter__(self) -> "FakeCrawlerContext":
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def arun(self, *, url: str) -> SimpleNamespace:
        self.requested_url = url
        return self.result


class JobCrawlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_extracts_job_and_infers_remote(self) -> None:
        result = SimpleNamespace(
            success=True,
            metadata={"title": "Junior Python Developer"},
            markdown=SimpleNamespace(
                raw_markdown="Work remotely with our Python engineering team."
            ),
            error_message=None,
        )
        context = FakeCrawlerContext(result)
        crawler = JobCrawler(crawler_factory=lambda: context)

        job = await crawler.crawl(
            CrawlJobRequest(
                source_url="https://careers.example.com/jobs/123",
                company="Example",
            )
        )

        self.assertEqual(job.title, "Junior Python Developer")
        self.assertEqual(job.company, "Example")
        self.assertTrue(job.is_remote)
        self.assertEqual(
            context.requested_url,
            "https://careers.example.com/jobs/123",
        )

    async def test_rejects_page_without_readable_content(self) -> None:
        result = SimpleNamespace(
            success=True,
            metadata={"title": "Junior Developer"},
            markdown=None,
            error_message=None,
        )
        crawler = JobCrawler(
            crawler_factory=lambda: FakeCrawlerContext(result),
        )

        with self.assertRaisesRegex(CrawlError, "readable job content"):
            await crawler.crawl(
                CrawlJobRequest(
                    source_url="https://careers.example.com/jobs/123",
                    company="Example",
                )
            )


class SourceAllowlistTests(unittest.TestCase):
    def test_allows_exact_host_and_subdomain(self) -> None:
        exact = CrawlJobRequest(
            source_url="https://example.com/job",
            company="Example",
        )
        subdomain = CrawlJobRequest(
            source_url="https://careers.example.com/job",
            company="Example",
        )

        self.assertTrue(source_host_is_allowed(exact.source_url, ["example.com"]))
        self.assertTrue(
            source_host_is_allowed(subdomain.source_url, ["example.com"])
        )

    def test_rejects_suffix_lookalike(self) -> None:
        request = CrawlJobRequest(
            source_url="https://evilexample.com/job",
            company="Example",
        )

        self.assertFalse(
            source_host_is_allowed(request.source_url, ["example.com"])
        )


class JobRepositoryTests(unittest.TestCase):
    def test_builds_parameterized_filters(self) -> None:
        filters, arguments = JobRepository._filters(
            query="junior python",
            location="London",
            remote=True,
        )

        self.assertEqual(
            arguments,
            ["junior python", "London", True],
        )
        self.assertIn("$1", filters[0])
        self.assertIn("$2", filters[1])
        self.assertIn("$3", filters[2])


if __name__ == "__main__":
    unittest.main()
