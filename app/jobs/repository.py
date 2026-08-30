from typing import Any

import asyncpg

from app.jobs.models import Job, JobList, JobUpsert


class JobRepository:
    def __init__(self, connection: asyncpg.Connection) -> None:
        self._connection = connection

    async def upsert(self, job: JobUpsert) -> Job:
        row = await self._connection.fetchrow(
            """
            INSERT INTO jobs (
                source_url,
                title,
                company,
                location,
                is_remote,
                description_markdown
            )
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (source_url) DO UPDATE SET
                title = EXCLUDED.title,
                company = EXCLUDED.company,
                location = EXCLUDED.location,
                is_remote = EXCLUDED.is_remote,
                description_markdown = EXCLUDED.description_markdown,
                updated_at = NOW()
            RETURNING *
            """,
            job.source_url,
            job.title,
            job.company,
            job.location,
            job.is_remote,
            job.description_markdown,
        )
        if row is None:
            raise RuntimeError("The job could not be saved")
        return Job.model_validate(dict(row))

    async def get(self, job_id: int) -> Job | None:
        row = await self._connection.fetchrow(
            "SELECT * FROM jobs WHERE id = $1",
            job_id,
        )
        return Job.model_validate(dict(row)) if row else None

    async def list(
        self,
        *,
        query: str | None,
        location: str | None,
        remote: bool | None,
        limit: int,
        offset: int,
    ) -> JobList:
        filters, arguments = self._filters(
            query=query,
            location=location,
            remote=remote,
        )
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        limit_position = len(arguments) + 1
        offset_position = len(arguments) + 2

        rows = await self._connection.fetch(
            f"""
            SELECT *
            FROM jobs
            {where}
            ORDER BY updated_at DESC, id DESC
            LIMIT ${limit_position}
            OFFSET ${offset_position}
            """,
            *arguments,
            limit,
            offset,
        )
        total = await self._connection.fetchval(
            f"SELECT COUNT(*) FROM jobs {where}",
            *arguments,
        )
        return JobList(
            items=[Job.model_validate(dict(row)) for row in rows],
            total=total,
            limit=limit,
            offset=offset,
        )

    @staticmethod
    def _filters(
        *,
        query: str | None,
        location: str | None,
        remote: bool | None,
    ) -> tuple[list[str], list[Any]]:
        filters: list[str] = []
        arguments: list[Any] = []

        if query:
            arguments.append(query)
            position = len(arguments)
            filters.append(
                "search_document @@ websearch_to_tsquery('english', "
                f"${position})"
            )
        if location:
            arguments.append(location)
            position = len(arguments)
            filters.append(f"location ILIKE '%' || ${position} || '%'")
        if remote is not None:
            arguments.append(remote)
            position = len(arguments)
            filters.append(f"is_remote = ${position}")

        return filters, arguments
