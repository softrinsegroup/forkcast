CREATE TABLE IF NOT EXISTS prompts (
    id      SERIAL PRIMARY KEY,
    prompt  TEXT NOT NULL,
    version INTEGER NOT NULL,
    active  BOOLEAN NOT NULL DEFAULT FALSE,
    model   VARCHAR(100),
    notes   TEXT,
    created_at TIMESTAMPTZ NOT NULL
)
