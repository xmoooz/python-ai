from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class CrawlJobRequest(BaseModel):
    source_url: HttpUrl
    company: str = Field(min_length=1, max_length=200)
    location: str | None = Field(default=None, max_length=200)
    is_remote: bool | None = None


class JobUpsert(BaseModel):
    source_url: str
    title: str
    company: str
    location: str | None = None
    is_remote: bool = False
    description_markdown: str


class Job(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_url: str
    title: str
    company: str
    location: str | None
    is_remote: bool
    description_markdown: str
    created_at: datetime
    updated_at: datetime


class JobList(BaseModel):
    items: list[Job]
    total: int
    limit: int
    offset: int
