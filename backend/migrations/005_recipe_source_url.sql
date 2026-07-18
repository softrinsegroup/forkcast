-- Source URL every recipe was parsed from.
-- Unique index is the dedup key for the scraper's ingest.
ALTER TABLE recipes ADD COLUMN source_url TEXT NOT NULL;

CREATE UNIQUE INDEX idx_recipes_source_url ON recipes (source_url);
