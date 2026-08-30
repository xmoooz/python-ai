CREATE TABLE jobs (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_url TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    location TEXT,
    is_remote BOOLEAN NOT NULL DEFAULT FALSE,
    description_markdown TEXT NOT NULL,
    search_document TSVECTOR GENERATED ALWAYS AS (
        setweight(to_tsvector('english', coalesce(title, '')), 'A')
        || setweight(to_tsvector('english', coalesce(company, '')), 'A')
        || setweight(to_tsvector('english', coalesce(location, '')), 'B')
        || setweight(
            to_tsvector('english', coalesce(description_markdown, '')),
            'C'
        )
    ) STORED,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX jobs_search_document_idx
    ON jobs
    USING GIN (search_document);

CREATE INDEX jobs_updated_at_idx
    ON jobs (updated_at DESC);
